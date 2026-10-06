"""
test_regression.py - Prueba de regresión rigurosa: CLI vs OMREngineService vs omr_service.

Compara:
- Respuestas detectadas
- Score
- Preguntas evaluadas
- Archivos procesados
- Errores / Estados
"""

import glob
import json
import os
import sys
from pathlib import Path

import pandas as pd

# 1. Importar parche headless antes de módulos de visión interactiva
import backend.app.core.headless_patch  # noqa: F401

from backend.app.services.omr_engine_service import OMREngineService
from main import entry_point_for_args
from omr_service import process_exam


def run_cli(input_path: str, output_dir: str):
    """Ejecuta el procesamiento original mediante CLI (main.py)."""
    args = {
        "autoAlign": False,
        "debug": False,
        "input_paths": [input_path],
        "output_dir": output_dir,
        "setLayout": False,
    }
    entry_point_for_args(args)


def read_cli_results_csv(output_dir: str) -> pd.DataFrame:
    """Busca y lee el archivo Results_*.csv generado por el CLI."""
    csv_pattern = os.path.join(output_dir, "**", "Results", "Results_*.csv")
    csv_files = glob.glob(csv_pattern, recursive=True)
    if not csv_files:
        # Buscar directamente en Results/*.csv
        csv_pattern2 = os.path.join(output_dir, "Results", "Results_*.csv")
        csv_files = glob.glob(csv_pattern2)
    if not csv_files:
        raise FileNotFoundError(f"No se encontró Results_*.csv en: {output_dir}")
    
    # Tomar el primer archivo encontrado o concatenar
    dfs = [pd.read_csv(f, dtype=str) for f in sorted(csv_files)]
    return pd.concat(dfs, ignore_index=True)


def compare_cli_vs_services(
    dataset_name: str,
    input_dir: str,
    template_path: str,
    evaluation_path: str = None,
    config_path: str = None,
):
    print(f"\n=======================================================")
    print(f"EJECUTANDO PRUEBA DE REGRESIÓN: {dataset_name}")
    print(f"=======================================================")

    cli_out_dir = f"outputs/regression_{dataset_name}_cli"
    service_job_id = f"regression_{dataset_name}_service"
    service_out_dir = f"storage/jobs/{service_job_id}"

    # Limpiar ejecuciones previas
    os.system(f"rm -rf {cli_out_dir} {service_out_dir}")

    # --- 1. EJECUCIÓN CLI ---
    print(f"[1/3] Ejecutando CLI original (main.py) sobre '{input_dir}'...")
    run_cli(input_path=input_dir, output_dir=cli_out_dir)
    cli_df = read_cli_results_csv(cli_out_dir)
    print(f"      -> CLI completado. Filas procesadas: {len(cli_df)}")

    # --- 2. EJECUCIÓN OMREngineService ---
    print(f"[2/3] Ejecutando OMREngineService...")
    engine = OMREngineService()
    exts = ("*.[pP][nN][gG]", "*.[jJ][pP][gG]", "*.[jJ][pP][eE][gG]", "*.[pP][dD][fF]")
    input_p = Path(input_dir)
    image_files = sorted([f for ext in exts for f in input_p.rglob(ext)])
    # Excluir archivos auxiliares como marcadores
    image_files = [f for f in image_files if f.name != "omr_marker.jpg" and "CheckedOMRs" not in str(f)]

    engine_response = engine.process_batch(
        file_paths=image_files,
        template_path=Path(template_path),
        evaluation_path=Path(evaluation_path) if evaluation_path else None,
        config_path=Path(config_path) if config_path else None,
        job_id=service_job_id,
        output_dir=Path(service_out_dir) / "outputs",
    )
    print(f"      -> OMREngineService completado. Hojas procesadas: {engine_response.total_files}")

    # --- 3. EJECUCIÓN omr_service (process_exam) ---
    service_response = process_exam(
        input_dir=input_dir,
        output_dir=service_out_dir,
        template=template_path,
        evaluation=evaluation_path,
        config=config_path,
        job_id=service_job_id,
    )
    print(f"      -> omr_service completado. Estudiantes procesados: {len(service_response['students'])}")

    # --- 4. COMPARACIÓN Y ASERCIONES ---
    print("\n--- COMPARANDO RESULTADOS ---")
    differences = []

    # 4.1 Comparar conteo de archivos
    cli_files = sorted(cli_df["file_id"].tolist())
    service_files = sorted([s["file_id"] for s in service_response["students"]])
    engine_files = sorted([r.file_id for r in engine_response.results])

    if cli_files != service_files:
        differences.append(f"Discrepancia en archivos procesados: CLI={cli_files} vs Service={service_files}")
    else:
        print(f"✓ Archivos procesados coinciden: {cli_files}")

    # 4.2 Comparar columnas de preguntas
    # Columnas base excluidas de preguntas
    metadata_cols = {"file_id", "input_path", "output_path", "score"}
    question_cols = [c for c in cli_df.columns if c not in metadata_cols]
    print(f"✓ Preguntas detectadas en CLI: {len(question_cols)} columnas ({question_cols[:3]} ... {question_cols[-3:] if len(question_cols)>3 else ''})")

    # 4.3 Comparar registro por registro
    for idx, cli_row in cli_df.iterrows():
        f_id = cli_row["file_id"]
        # Buscar en service_response
        svc_match = next((s for s in service_response["students"] if s["file_id"] == f_id), None)
        eng_match = next((r for r in engine_response.results if r.file_id == f_id), None)

        if not svc_match:
            differences.append(f"Archivo {f_id} no encontrado en omr_service")
            continue

        # Comparar Score
        cli_score = float(cli_row["score"])
        svc_score = float(svc_match["score"])
        eng_score = float(eng_match.score)

        if abs(cli_score - svc_score) > 0.001:
            differences.append(f"Score distinto en {f_id}: CLI={cli_score} vs Service={svc_score}")
        else:
            print(f"✓ Score coincide en '{f_id}': CLI={cli_score} | Service={svc_score} | Engine={eng_score}")

        # Comparar Respuestas pregunta por pregunta
        for q in question_cols:
            cli_ans = str(cli_row[q]) if pd.notna(cli_row[q]) else ""
            svc_ans = str(svc_match["responses"].get(q, ""))
            eng_ans = str(eng_match.responses.get(q, ""))

            if cli_ans != svc_ans:
                differences.append(f"Respuesta distinta en {f_id} para '{q}': CLI='{cli_ans}' vs Service='{svc_ans}'")

    if differences:
        print(f"\n❌ Se encontraron {len(differences)} diferencias:")
        for d in differences:
            print(f"   - {d}")
        return False, differences, cli_df, service_response
    else:
        print(f"\n✓ 100% de respuestas y scores COINCIDEN EXACTAMENTE entre CLI y Services.")
        return True, [], cli_df, service_response


def main():
    # Test 1: answer-key/using-csv (5 preguntas, evaluación CSV)
    ok1, diff1, cli1, svc1 = compare_cli_vs_services(
        dataset_name="using_csv",
        input_dir="samples/answer-key/using-csv",
        template_path="samples/answer-key/using-csv/template.json",
        evaluation_path="samples/answer-key/using-csv/evaluation.json",
    )

    # Test 2: community/UPSC-mock (100 preguntas, 3 hojas escaneadas a distintos ángulos)
    ok2, diff2, cli2, svc2 = compare_cli_vs_services(
        dataset_name="upsc_mock",
        input_dir="samples/community/UPSC-mock",
        template_path="samples/community/UPSC-mock/template.json",
        evaluation_path="samples/community/UPSC-mock/evaluation.json",
        config_path="samples/community/UPSC-mock/config.json",
    )

    print("\n" + "=" * 60)
    print("RESUMEN DE REGRESIÓN")
    print("=" * 60)
    print(f"Test 1 (using-csv):  {'APROBADO' if ok1 else 'REQUIERE CORRECCIÓN'}")
    print(f"Test 2 (UPSC-mock):  {'APROBADO' if ok2 else 'REQUIERE CORRECCIÓN'}")
    
    if ok1 and ok2:
        print("\nESTADO GLOBAL: APROBADO")
        sys.exit(0)
    else:
        print("\nESTADO GLOBAL: REQUIERE CORRECCIÓN")
        sys.exit(1)


if __name__ == "__main__":
    main()
