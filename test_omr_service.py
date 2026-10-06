"""
test_omr_service.py - Prueba mínima de integración para omr_service.py.
Verifica que el servicio produzca exactamente los mismos resultados que el motor original.
"""

import json
from pathlib import Path
from omr_service import OMRError, process_exam


def test_process_sample5():
    print("\n--- INICIANDO PRUEBA 1: omr_service con sample5 (evaluación y multi-marcada) ---")

    input_dir = "samples/sample5/ScanBatch1"
    template_path = "samples/sample5/template.json"
    eval_path = "samples/sample5/evaluation.json"
    config_path = "samples/sample5/config.json"
    job_id = "test_job_sample5"
    output_dir = f"storage/jobs/{job_id}"

    result = process_exam(
        input_dir=input_dir,
        output_dir=output_dir,
        template=template_path,
        evaluation=eval_path,
        config=config_path,
        job_id=job_id,
    )

    # 1. Validar estructura general
    assert isinstance(result, dict), "El resultado debe ser un diccionario"
    assert "exam" in result, "Falta la clave 'exam' en el resultado"
    assert "students" in result, "Falta la clave 'students' en el resultado"
    assert "outputs" in result, "Falta la clave 'outputs' en el resultado"

    # 2. Validar datos del examen
    exam = result["exam"]
    assert exam["job_id"] == job_id
    assert exam["total_students"] == 1
    print(f"✓ Examen validado: {exam['total_students']} estudiante(s) procesado(s).")

    # 3. Validar datos del estudiante
    student = result["students"][0]
    assert student["file_id"] == "camscanner-1.jpg"
    assert student["multi_marked"] is True, "Debe detectar que tiene marcas múltiples en q18 (AD)"
    assert student["status"] == "MULTI_MARKED", f"Estado esperado MULTI_MARKED, obtenido: {student['status']}"
    assert student["score"] == -4.0, f"Score esperado: -4.0, obtenido: {student['score']}"
    print(f"✓ Estudiante validado: {student['file_id']} con Score: {student['score']} y status: {student['status']}")

    # 4. Validar respuestas detectadas clave
    responses = student["responses"]
    assert responses.get("q1") == "D", f"q1 esperado 'D', obtenido '{responses.get('q1')}'"
    assert responses.get("q2") == "C", f"q2 esperado 'C', obtenido '{responses.get('q2')}'"
    assert responses.get("q4") == "C", f"q4 esperado 'C', obtenido '{responses.get('q4')}'"
    assert responses.get("q18") == "AD", f"q18 esperado 'AD', obtenido '{responses.get('q18')}'"
    assert responses.get("Roll") == "E204420102", f"Roll esperado 'E204420102', obtenido '{responses.get('Roll')}'"
    print("✓ Respuestas de burbujas verificadas (q1=D, q2=C, q4=C, q18=AD, Roll=E204420102).")

    # 5. Validar archivos de salida generados
    out_img = Path(output_dir) / "outputs" / "marked_camscanner-1.jpg"
    assert out_img.exists(), f"La imagen procesada no fue creada en: {out_img}"

    out_csv = Path(output_dir) / "results" / "Results.csv"
    assert out_csv.exists(), f"El archivo CSV no fue creado en: {out_csv}"

    out_json = Path(output_dir) / "results" / "results.json"
    assert out_json.exists(), f"El archivo results.json no fue creado en: {out_json}"
    print("✓ Archivos de salida verificados (imagen marcada, Results.csv, results.json).")

    # 6. Validar que results.json es válido y coincide
    with out_json.open("r", encoding="utf-8") as f:
        saved_json = json.load(f)
    assert saved_json["exam"]["job_id"] == job_id
    assert saved_json["students"][0]["score"] == -4.0
    print("✓ Archivo results.json contiene los mismos datos estructurados.")


def test_process_sample1():
    print("\n--- INICIANDO PRUEBA 2: omr_service con sample1 (Roll + MCQ) ---")

    input_dir = "samples/sample1/MobileCamera"
    template_path = "samples/sample1/template.json"
    config_path = "samples/sample1/config.json"
    job_id = "test_job_sample1"
    output_dir = f"storage/jobs/{job_id}"

    result = process_exam(
        input_dir=input_dir,
        output_dir=output_dir,
        template=template_path,
        config=config_path,
        job_id=job_id,
    )

    student = result["students"][0]
    assert student["file_id"] == "sheet1.jpg"
    assert student["status"] == "SUCCESS"
    assert student["multi_marked"] is False
    assert student["responses"].get("Roll") == "E503110026", f"Roll esperado 'E503110026', obtenido '{student['responses'].get('Roll')}'"
    print(f"✓ Sample1 procesado con éxito: Roll={student['responses'].get('Roll')}, status={student['status']}")


def test_error_handling():
    print("\n--- INICIANDO PRUEBA 3: Manejo de errores en omr_service ---")
    # Caso 1: Directorio de entrada inexistente
    try:
        process_exam(input_dir="directorio_inexistente_xyz")
        assert False, "Debió haber lanzado OMRError en VALIDATION"
    except OMRError as err:
        assert err.stage == "VALIDATION"
        print(f"✓ Error capturado correctamente en etapa [{err.stage}]: {err.message}")

    # Caso 2: Template inexistente
    try:
        process_exam(input_dir="samples/sample1/MobileCamera", template="template_inexistente.json")
        assert False, "Debió haber lanzado OMRError en VALIDATION"
    except OMRError as err:
        assert err.stage == "VALIDATION"
        print(f"✓ Error capturado correctamente en etapa [{err.stage}]: {err.message}")

    print("✓ Manejo de errores validado en todas las etapas.")


if __name__ == "__main__":
    test_process_sample5()
    test_process_sample1()
    test_error_handling()
    print("\n=======================================================")
    print("TODAS LAS PRUEBAS COMPLETADAS CON ÉXITO")
    print("=======================================================")
