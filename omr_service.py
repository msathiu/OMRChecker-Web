"""
omr_service.py - Servicio de integración Python para OMRChecker.

Permite ejecutar el procesamiento y evaluación de hojas OMR programáticamente desde código,
sin necesidad de invocar 'python main.py' mediante subprocess y reutilizando directamente
las clases nativas del motor OMRChecker.
"""

import csv
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import cv2
import numpy as np
import pandas as pd

# Parche defensivo para entornos headless (evita excepciones de screeninfo o cv2.imshow)
import backend.app.core.headless_patch  # noqa: F401

from src.defaults import CONFIG_DEFAULTS
from src.evaluation import EvaluationConfig
from src.template import Template
from src.utils.image import ImageUtils
from src.utils.parsing import get_concatenated_response, open_config_with_defaults


class OMRErrorStage(str, Enum):
    VALIDATION = "VALIDATION"
    INITIALIZATION = "INITIALIZATION"
    PREPROCESSING = "PREPROCESSING"
    READING_OMR = "READING_OMR"
    EVALUATION = "EVALUATION"
    OUTPUT_GENERATION = "OUTPUT_GENERATION"
    CSV_PARSING = "CSV_PARSING"


class OMRError(Exception):
    """Excepción estructurada para capturar fallos identificando la etapa exacta."""

    def __init__(self, stage: OMRErrorStage, message: str, original_error: Optional[Exception] = None):
        super().__init__(f"[{stage.value}] {message}")
        self.stage = stage.value
        self.message = message
        self.original_error = original_error


def process_exam(
    input_dir: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    template: Optional[Union[str, Path]] = None,
    evaluation: Optional[Union[str, Path]] = None,
    config: Optional[Union[str, Path]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ejecuta el procesamiento OMR sobre un directorio de imágenes/PDFs.

    Args:
        input_dir: Directorio con hojas OMR (.jpg, .png, .pdf).
        output_dir: Directorio base donde se guardarán outputs (imágenes marcadas, CSV, JSON).
                    Si no se indica, usa 'storage/jobs/{job_id}'.
        template: Ruta al archivo template.json. Si no se indica, busca en input_dir.
        evaluation: Ruta al archivo evaluation.json (opcional). Si no se indica, busca en input_dir.
        config: Ruta a config.json (opcional). Si no se indica, usa defaults de OMRChecker.
        job_id: Identificador único del trabajo (opcional, autogenerado si no se proporciona).

    Returns:
        Dict con estructura de resultados (exam, students, outputs).
    """
    # 1. ETAPA DE VALIDACIÓN
    stage = OMRErrorStage.VALIDATION
    try:
        input_path = Path(input_dir).resolve()
        if not input_path.exists() or not input_path.is_dir():
            raise FileNotFoundError(f"El directorio de entrada no existe: '{input_path}'")

        if not job_id:
            job_id = str(uuid.uuid4())

        root_dir = Path(__file__).resolve().parent
        if output_dir is None:
            base_output_path = root_dir / "storage" / "jobs" / job_id
        else:
            base_output_path = Path(output_dir).resolve()

        outputs_marked_dir = base_output_path / "outputs"
        results_dir = base_output_path / "results"
        outputs_marked_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)

        # Resolver template
        if template is not None:
            template_path = Path(template).resolve()
        else:
            template_path = input_path / "template.json"

        if not template_path.exists():
            raise FileNotFoundError(f"No se encontró template.json en: '{template_path}'")

        # Resolver evaluation (opcional)
        evaluation_path = None
        if evaluation is not None:
            eval_candidate = Path(evaluation).resolve()
            if eval_candidate.exists():
                evaluation_path = eval_candidate
            else:
                raise FileNotFoundError(f"El archivo evaluation indicado no existe: '{eval_candidate}'")
        else:
            default_eval = input_path / "evaluation.json"
            if default_eval.exists():
                evaluation_path = default_eval

        # Resolver config (opcional)
        config_path = None
        if config is not None:
            cfg_candidate = Path(config).resolve()
            if cfg_candidate.exists():
                config_path = cfg_candidate
        else:
            default_cfg = input_path / "config.json"
            if default_cfg.exists():
                config_path = default_cfg

        # Buscar archivos OMR a procesar (soporte recursivo para subdirectorios igual que CLI)
        exts = ("*.[pP][nN][gG]", "*.[jJ][pP][gG]", "*.[jJ][pP][eE][gG]", "*.[pP][dD][fF]")
        omr_files = sorted([f for ext in exts for f in input_path.rglob(ext)])

        # Excluir marcadores y referencias conocidas si están en input_path
        excluded_names = {"omr_marker.jpg"}
        omr_files = [
            f for f in omr_files
            if f.name not in excluded_names and "CheckedOMRs" not in f.parts and "outputs" not in f.parts
        ]

        if not omr_files:
            raise FileNotFoundError(f"No se encontraron imágenes o PDFs válidos en: '{input_path}'")

    except Exception as e:
        raise OMRError(stage, f"Error en validación de entradas: {str(e)}", e)

    # 2. ETAPA DE INICIALIZACIÓN
    stage = OMRErrorStage.INITIALIZATION
    try:
        if config_path:
            tuning_config = open_config_with_defaults(config_path)
        else:
            tuning_config = deepcopy(CONFIG_DEFAULTS)

        # Forzar desactivación de GUI y stacks innecesarios en modo servicio
        tuning_config.outputs.show_image_level = 0
        tuning_config.outputs.save_image_level = 0
        tuning_config.outputs.save_detections = False

        # Instanciar Template nativo de OMRChecker
        template_instance = Template(template_path, tuning_config)

        # Instanciar EvaluationConfig nativo si se dispone de pauta
        evaluation_instance = None
        if evaluation_path:
            evaluation_instance = EvaluationConfig(
                curr_dir=evaluation_path.parent,
                evaluation_path=evaluation_path,
                template=template_instance,
                tuning_config=tuning_config,
            )

    except Exception as e:
        raise OMRError(stage, f"Error al inicializar template o evaluación de OMRChecker: {str(e)}", e)

    # 3, 4, 5. PROCESAMIENTO POR HOJA
    raw_sheet_results = []
    marked_images_saved = []

    for file_path in omr_files:
        try:
            # Carga nativa de imágenes / descomposición de PDFs con PyMuPDF
            images = ImageUtils.load_omr_image(file_path, tuning_config)
        except Exception as e:
            raise OMRError(OMRErrorStage.PREPROCESSING, f"Fallo al abrir archivo '{file_path.name}': {str(e)}", e)

        for img_name, in_omr in images:
            # PREPROCESAMIENTO (CropPage / CropOnMarkers)
            stage = OMRErrorStage.PREPROCESSING
            try:
                processed_omr = template_instance.image_instance_ops.apply_preprocessors(
                    img_name, in_omr, template_instance
                )
            except Exception as e:
                raise OMRError(stage, f"Error en preprocesadores para '{img_name}': {str(e)}", e)

            if processed_omr is None:
                # Marcadores no encontrados o error en contorno de página
                raw_sheet_results.append(
                    {
                        "file_id": img_name,
                        "original_name": file_path.name,
                        "input_path": str(file_path),
                        "output_image_path": "",
                        "score": 0.0,
                        "status": "ERROR",
                        "error_message": "Marcadores o bordes de página no detectados",
                        "multi_marked": False,
                        "responses": {},
                        "answers": [],
                    }
                )
                continue

            # LECTURA OMR (Muestreo de píxeles y umbrales)
            stage = OMRErrorStage.READING_OMR
            try:
                (
                    response_dict,
                    final_marked,
                    multi_marked,
                    _multi_roll,
                ) = template_instance.image_instance_ops.read_omr_response(
                    template_instance,
                    image=processed_omr,
                    name=img_name,
                    save_dir=None,
                )
                # Concatenar respuestas según customLabels
                concatenated_response = get_concatenated_response(response_dict, template_instance)
            except Exception as e:
                raise OMRError(stage, f"Error al leer burbujas OMR en '{img_name}': {str(e)}", e)

            # GUARDAR IMAGEN PROCESADA CON MARCAS
            stage = OMRErrorStage.OUTPUT_GENERATION
            try:
                output_image_path = outputs_marked_dir / f"marked_{img_name}"
                ImageUtils.save_img(str(output_image_path), final_marked)
                marked_images_saved.append(str(output_image_path))
            except Exception as e:
                raise OMRError(stage, f"Error al guardar imagen procesada '{img_name}': {str(e)}", e)

            # EVALUACIÓN Y CALIFICACIÓN
            stage = OMRErrorStage.EVALUATION
            score = 0.0
            answers_audit = []
            max_score = 0.0

            if evaluation_instance is not None:
                try:
                    evaluation_instance.reset_explanation_table()
                    current_score = 0.0

                    for q in evaluation_instance.questions_in_order:
                        marked_ans = concatenated_response.get(q, template_instance.global_empty_val)
                        matcher = evaluation_instance.question_to_answer_matcher[q]
                        verdict, delta = matcher.get_verdict_marking(marked_ans)
                        current_score += delta

                        delta_correct = matcher.marking.get("correct", 1.0)
                        if isinstance(delta_correct, (int, float)):
                            max_score += delta_correct

                        section_label = (
                            matcher.get_section_explanation()
                            if evaluation_instance.has_non_default_section
                            else "DEFAULT"
                        )

                        answers_audit.append(
                            {
                                "question": q,
                                "marked": str(marked_ans),
                                "allowed_answers": str(matcher),
                                "verdict": str.title(verdict),
                                "delta": round(float(delta), 2),
                                "score": round(float(current_score), 2),
                                "section": section_label,
                            }
                        )

                    score = float(current_score)
                except Exception as e:
                    raise OMRError(stage, f"Error al evaluar respuestas en '{img_name}': {str(e)}", e)

            percentage = None
            if max_score > 0:
                percentage = round(max(0.0, (score / max_score) * 100), 2)

            has_multi = bool(multi_marked)
            raw_sheet_results.append(
                {
                    "file_id": img_name,
                    "original_name": file_path.name,
                    "input_path": str(file_path),
                    "output_image_path": str(output_image_path),
                    "score": score,
                    "total": round(max_score, 2) if max_score > 0 else None,
                    "percentage": percentage,
                    "status": "MULTI_MARKED" if has_multi else "SUCCESS",
                    "error_message": "",
                    "multi_marked": has_multi,
                    "responses": concatenated_response,
                    "answers": answers_audit,
                }
            )

    # 6. GENERAR EL CSV DE RESULTADOS (Salida estándar de OMRChecker)
    stage = OMRErrorStage.OUTPUT_GENERATION
    try:
        csv_file_path = results_dir / "Results.csv"
        sheet_cols = ["file_id", "input_path", "output_path", "score"] + template_instance.output_columns
        csv_rows = []

        for item in raw_sheet_results:
            resp_cols = [item["responses"].get(col, "") for col in template_instance.output_columns]
            row = [item["file_id"], item["input_path"], item["output_image_path"], item["score"]] + resp_cols
            csv_rows.append(row)

        df_csv = pd.DataFrame(csv_rows, columns=sheet_cols, dtype=str)
        df_csv.to_csv(csv_file_path, index=False, quoting=csv.QUOTE_NONNUMERIC)

    except Exception as e:
        raise OMRError(stage, f"Error al generar el archivo CSV de resultados: {str(e)}", e)

    # 7 & 8. LEER EL CSV GENERADO Y CONVERTIR EN ESTRUCTURAS PYTHON
    stage = OMRErrorStage.CSV_PARSING
    try:
        parsed_csv_df = pd.read_csv(csv_file_path, dtype=str)
        csv_records = parsed_csv_df.to_dict(orient="records")
    except Exception as e:
        raise OMRError(stage, f"Error al leer y parsear el archivo CSV generado: {str(e)}", e)

    # 9. CONSTRUIR Y GUARDAR results.json ESTRUCTURADO
    try:
        valid_scores = [r["score"] for r in raw_sheet_results if r["status"] != "ERROR"]
        avg_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0
        high_score = max(valid_scores) if valid_scores else 0.0
        low_score = min(valid_scores) if valid_scores else 0.0

        max_exam_score = raw_sheet_results[0]["total"] if (raw_sheet_results and raw_sheet_results[0]["total"]) else None
        total_questions = len(template_instance.output_columns)

        structured_result = {
            "exam": {
                "job_id": job_id,
                "template_path": str(template_path),
                "evaluation_path": str(evaluation_path) if evaluation_path else None,
                "total_students": len(raw_sheet_results),
                "total_questions": total_questions,
                "max_possible_score": max_exam_score,
                "average_score": avg_score,
                "highest_score": high_score,
                "lowest_score": low_score,
                "created_at": datetime.utcnow().isoformat(),
            },
            "students": raw_sheet_results,
            "csv_records": csv_records,
            "outputs": {
                "results_csv": str(csv_file_path),
                "results_json": str(results_dir / "results.json"),
                "marked_images": marked_images_saved,
            },
        }

        # Guardar results.json
        json_file_path = results_dir / "results.json"
        with json_file_path.open("w", encoding="utf-8") as f:
            json.dump(structured_result, f, indent=2, ensure_ascii=False)

        # También guardar copia en base_output_path si difiere de results_dir
        root_json_path = base_output_path / "results.json"
        if root_json_path != json_file_path:
            with root_json_path.open("w", encoding="utf-8") as f:
                json.dump(structured_result, f, indent=2, ensure_ascii=False)

    except Exception as e:
        raise OMRError(OMRErrorStage.OUTPUT_GENERATION, f"Error al generar results.json estructurado: {str(e)}", e)

    return structured_result

