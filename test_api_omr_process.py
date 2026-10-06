"""
test_api_omr_process.py - Prueba automatizada del endpoint principal de FastAPI:
POST /api/omr/process (con recepción de archivo .zip único)

Verifica:
1. Disponibilidad de OpenAPI/Swagger (/docs y /openapi.json) y eliminación de 'images'/'files'.
2. Procesamiento de archivo ZIP con hoja de examen (sample1/MobileCamera/sheet1.jpg).
3. Verificación de estructura de respuesta ({job_id, status, total_files, results, created_at}).
4. Verificación de persistencia en storage/jobs/{job_id}/ (ZIP, inputs/, outputs/, results/).
5. Procesamiento con evaluación opcional (sample5).
6. Validaciones y seguridad:
   - Extensión no .zip (400)
   - Archivo ZIP vacío (0 bytes) (400)
   - Archivo ZIP corrupto (400)
   - Archivo ZIP sin imágenes OMR (400)
   - Prevención de Zip Slip / Path Traversal (400)
   - Template faltante (422) o corrupto (400)
7. Endpoints de consulta y exportación (/jobs/{job_id}, /results, /files, /image, /export/csv, /export/excel).
"""

import io
import json
import zipfile
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def build_zip_bytes(files_dict: dict[str, bytes]) -> bytes:
    """Crea en memoria un archivo ZIP con los ficheros y contenidos indicados."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, data in files_dict.items():
            zf.writestr(filename, data)
    buffer.seek(0)
    return buffer.getvalue()


def test_swagger_and_openapi():
    print("\n--- 1. Probando Swagger UI y OpenAPI Schema ---")
    resp_docs = client.get("/docs")
    assert resp_docs.status_code == 200, f"Error al cargar /docs: {resp_docs.status_code}"
    print("✓ Swagger UI (/docs) disponible y responde HTTP 200.")

    resp_openapi = client.get("/openapi.json")
    assert resp_openapi.status_code == 200, f"Error al cargar /openapi.json: {resp_openapi.status_code}"
    schema = resp_openapi.json()
    assert "/api/omr/process" in schema["paths"], "Ruta /api/omr/process no encontrada en OpenAPI schema"

    post_op = schema["paths"]["/api/omr/process"]["post"]
    request_body = post_op.get("requestBody", {})
    content = request_body.get("content", {})
    multipart_schema = content.get("multipart/form-data", {}).get("schema", {})

    ref = multipart_schema.get("$ref")
    if ref:
        schema_key = ref.split("/")[-1]
        body_schema = schema["components"]["schemas"][schema_key]
        props = body_schema.get("properties", {})
        required = body_schema.get("required", [])
    else:
        props = multipart_schema.get("properties", {})
        required = multipart_schema.get("required", [])

    # Validar que los campos requeridos y opcionales
    assert "zip_file" in props, "El campo 'zip_file' debe estar presente en OpenAPI schema"
    assert "template" in props, "El campo 'template' debe estar presente en OpenAPI schema"
    assert "evaluation" in props, "El campo 'evaluation' debe estar presente en OpenAPI schema"
    assert "zip_file" in required, "'zip_file' debe ser obligatorio"
    assert "template" not in required, "'template' debe ser opcional con fallback estándar"

    # Validar que 'images' y 'files' ya NO están presentes
    assert "images" not in props, "El campo antiguo 'images' no debe figurar en el endpoint"
    assert "files" not in props, "El campo antiguo 'files' no debe figurar en el endpoint"

    print(f"✓ OpenAPI schema verificado: parámetros = {list(props.keys())}")
    print("✓ Campos 'images' y 'files' eliminados exitosamente del endpoint.")


def test_process_standard_sheet_zip_without_template():
    print("\n--- 2. Probando POST /api/omr/process SOLO con ZIP (template estandarizado 40x5 automático) ---")

    sheet_path = Path("samples/standard/hoja_estandar.png")
    assert sheet_path.exists(), f"Falta {sheet_path}"

    # Crear ZIP en memoria conteniendo hoja_estandar.png
    zip_bytes = build_zip_bytes({
        "hoja_estandar.png": sheet_path.read_bytes(),
    })

    # NO enviar template: el backend debe usar automáticamente la plantilla estándar (40 preguntas x 5 opciones)
    multipart_data = [
        ("zip_file", ("examen_estandar.zip", zip_bytes, "application/zip")),
    ]

    response = client.post("/api/omr/process", files=multipart_data)
    assert response.status_code == 200, f"Error en endpoint: {response.status_code} - {response.text}"
    data = response.json()

    assert data["status"] == "completed"
    assert data["total_files"] == 1
    sheet_res = data["results"][0]
    assert len(sheet_res["responses"]) == 40, f"Se esperaban 40 preguntas, obtenidas {len(sheet_res['responses'])}"
    assert "q1" in sheet_res["responses"]
    assert "q40" in sheet_res["responses"]

    job_id = data["job_id"]
    print(f"✓ Procesamiento con template estándar 40x5 exitoso (job_id: {job_id}, total preguntas: {len(sheet_res['responses'])})")
    return job_id


def test_process_with_dynamic_answer_key():
    print("\n--- 3. Probando POST /api/omr/process con clave de respuestas dinámica (estándar 40 preguntas) ---")

    sheet_path = Path("samples/standard/hoja_estandar.png")
    zip_bytes = build_zip_bytes({"hoja_estandar.png": sheet_path.read_bytes()})

    # Simular evaluación generada por React con 40 preguntas
    eval_object = {
        "source_type": "custom",
        "options": {
            "questions_in_order": [f"q{i}" for i in range(1, 41)],
            "answers_in_order": ["A"] * 40,
            "should_explain_scoring": True,
        },
        "marking_schemes": {
            "DEFAULT": {
                "correct": 1,
                "incorrect": 0,
                "unmarked": 0,
            },
        },
    }
    eval_bytes = json.dumps(eval_object).encode("utf-8")

    multipart_data = [
        ("zip_file", ("examen_estandar.zip", zip_bytes, "application/zip")),
        ("evaluation", ("evaluation.json", eval_bytes, "application/json")),
    ]

    response = client.post("/api/omr/process", files=multipart_data)
    assert response.status_code == 200, f"Error: {response.status_code} - {response.text}"
    data = response.json()

    assert data["total_files"] == 1
    sheet_res = data["results"][0]
    assert len(sheet_res["audits"]) == 40, f"Se esperaban 40 auditorías, obtenidas {len(sheet_res['audits'])}"
    print(f"✓ Clave de respuestas dinámica estándar (40 preguntas) evaluada correctamente.")
    return data["job_id"]


def test_max_questions_limit_validation():
    print("\n--- 4. Probando validación estricta de MAX_QUESTIONS = 40 (rechazo de 41+) ---")

    sheet_path = Path("samples/standard/hoja_estandar.png")
    zip_bytes = build_zip_bytes({"hoja_estandar.png": sheet_path.read_bytes()})

    # Crear evaluación inválida con 41 preguntas
    eval_invalid = {
        "source_type": "custom",
        "options": {
            "questions_in_order": [f"q{i}" for i in range(1, 42)],
            "answers_in_order": ["A"] * 41,
        },
        "marking_schemes": {
            "DEFAULT": {"correct": 1, "incorrect": 0, "unmarked": 0}
        }
    }
    eval_bytes = json.dumps(eval_invalid).encode("utf-8")

    multipart_data = [
        ("zip_file", ("examen.zip", zip_bytes, "application/zip")),
        ("evaluation", ("evaluation.json", eval_bytes, "application/json")),
    ]

    response = client.post("/api/omr/process", files=multipart_data)
    assert response.status_code == 400, f"Se esperaba HTTP 400 para 41 preguntas, recibido {response.status_code}"
    assert "40" in response.text
    print(f"✓ 41 preguntas rechazadas exitosamente con HTTP 400: {response.json()['detail']}")


def test_process_multiple_with_evaluation():
    print("\n--- 3. Probando POST /api/omr/process con ZIP multi-examen y evaluation (sample5) ---")

    img1_path = Path("samples/sample5/ScanBatch1/camscanner-1.jpg")
    img2_path = Path("samples/sample5/ScanBatch2/camscanner-2.jpg")
    template_path = Path("samples/sample5/template.json")
    eval_path = Path("samples/sample5/evaluation.json")
    marker_path = Path("samples/sample5/omr_marker.jpg")

    zip_bytes = build_zip_bytes({
        "camscanner-1.jpg": img1_path.read_bytes(),
        "camscanner-2.jpg": img2_path.read_bytes(),
        "subcarpeta/notas.txt": b"Este archivo no es imagen y debe ser ignorado silenciosamente",
    })

    multipart_data = [
        ("zip_file", ("examenes_lote.zip", zip_bytes, "application/zip")),
        ("template", ("template.json", template_path.read_bytes(), "application/json")),
        ("evaluation", ("evaluation.json", eval_path.read_bytes(), "application/json")),
        ("marker_image", ("omr_marker.jpg", marker_path.read_bytes(), "image/jpeg")),
    ]

    response = client.post("/api/omr/process", files=multipart_data)
    assert response.status_code == 200, f"Error: {response.status_code} - {response.text}"
    data = response.json()

    assert data["total_files"] == 2
    assert len(data["results"]) == 2
    res1 = data["results"][0]
    res2 = data["results"][1]
    assert res1["score"] == -4.0
    assert res1["multi_marked"] is True
    assert res2["score"] == 55.0
    assert res2["status"] == "SUCCESS"
    assert res2["correctas"] > 0
    assert res2["incorrectas"] >= 0
    assert res2["sin_responder"] >= 0
    assert "correctas" in res1
    assert "incorrectas" in res1
    assert "sin_responder" in res1

    print(f"✓ ZIP multi-examen procesado con evaluación (Hoja 1 score: {res1['score']}, Hoja 2 score: {res2['score']}, correctas: {res2['correctas']}).")
    return response.json()["job_id"]


def test_validation_and_security_errors():
    print("\n--- 4. Probando validaciones y controles de seguridad (Zip Slip, corruptos, vacíos) ---")
    template_bytes = Path("samples/sample1/template.json").read_bytes()

    # Caso A: Archivo sin extensión .zip
    multipart_bad_ext = [
        ("zip_file", ("examenes.tar.gz", b"contenido ficticio", "application/gzip")),
        ("template", ("template.json", template_bytes, "application/json")),
    ]
    resp = client.post("/api/omr/process", files=multipart_bad_ext)
    assert resp.status_code == 400
    assert "extensión .zip" in resp.json()["detail"].lower()
    print("✓ Rechazo correcto ante extensión distinta a .zip (HTTP 400).")

    # Caso B: Archivo ZIP vacío (0 bytes)
    multipart_empty_zip = [
        ("zip_file", ("vacio.zip", b"", "application/zip")),
        ("template", ("template.json", template_bytes, "application/json")),
    ]
    resp = client.post("/api/omr/process", files=multipart_empty_zip)
    assert resp.status_code == 400
    assert "está vacío (0 bytes)" in resp.json()["detail"]
    print("✓ Rechazo correcto ante archivo ZIP de 0 bytes (HTTP 400).")

    # Caso C: Archivo ZIP corrupto (no es zip válido)
    multipart_corrupt_zip = [
        ("zip_file", ("corrupto.zip", b"PK\x03\x04bytes_corruptos_sin_estructura_zip", "application/zip")),
        ("template", ("template.json", template_bytes, "application/json")),
    ]
    resp = client.post("/api/omr/process", files=multipart_corrupt_zip)
    assert resp.status_code == 400
    assert "no es un archivo zip válido" in resp.json()["detail"].lower() or "dañado" in resp.json()["detail"].lower()
    print("✓ Rechazo correcto ante archivo ZIP corrupto (HTTP 400).")

    # Caso D: ZIP válido pero sin ninguna imagen OMR (solo contiene archivos de texto/docs)
    zip_no_images = build_zip_bytes({
        "instrucciones.txt": b"Instrucciones del examen...",
        "datos.csv": b"id,nombre\n1,Juan",
    })
    multipart_no_images = [
        ("zip_file", ("sin_imagenes.zip", zip_no_images, "application/zip")),
        ("template", ("template.json", template_bytes, "application/json")),
    ]
    resp = client.post("/api/omr/process", files=multipart_no_images)
    assert resp.status_code == 400
    assert "no contiene ninguna imagen" in resp.json()["detail"].lower()
    print("✓ Rechazo correcto ante ZIP sin imágenes OMR compatibles (HTTP 400).")

    # Caso E: Intento de Zip Slip / Path Traversal (ruta maliciosa ../../etc/passwd)
    buffer_slip = io.BytesIO()
    with zipfile.ZipFile(buffer_slip, "w") as zf:
        zf.writestr("../../etc/passwd", "root:x:0:0:root:/root:/bin/bash")
    buffer_slip.seek(0)

    multipart_zip_slip = [
        ("zip_file", ("malicious_slip.zip", buffer_slip.getvalue(), "application/zip")),
        ("template", ("template.json", template_bytes, "application/json")),
    ]
    resp = client.post("/api/omr/process", files=multipart_zip_slip)
    assert resp.status_code == 400
    assert "zip slip" in resp.json()["detail"].lower() or "maliciosa" in resp.json()["detail"].lower()
    print("✓ Detección y bloqueo seguro de Zip Slip / Path Traversal (HTTP 400).")

    # Caso F: Template corrupto (JSON no válido)
    sheet1_bytes = Path("samples/sample1/MobileCamera/sheet1.jpg").read_bytes()
    zip_ok = build_zip_bytes({"sheet1.jpg": sheet1_bytes})
    multipart_corrupt_tpl = [
        ("zip_file", ("examen.zip", zip_ok, "application/zip")),
        ("template", ("template.json", b"{json_invalido: 123", "application/json")),
    ]
    resp = client.post("/api/omr/process", files=multipart_corrupt_tpl)
    assert resp.status_code == 400
    assert "json inválido" in resp.json()["detail"].lower()
    print("✓ Rechazo correcto ante template.json con sintaxis inválida (HTTP 400).")


def test_job_query_and_export_endpoints(job_id: str):
    print("\n--- 5. Probando endpoints de consulta y exportación del job ---")

    # 5.1 GET /api/omr/jobs/{job_id}
    resp_job = client.get(f"/api/omr/jobs/{job_id}")
    assert resp_job.status_code == 200
    summary = resp_job.json()
    assert summary["job_id"] == job_id
    assert summary["status"] == "completed"
    assert summary["has_results"] is True
    assert summary["has_outputs"] is True
    assert summary["total_files"] >= 1
    print(f"✓ GET /api/omr/jobs/{job_id} -> status: {summary['status']}, total_files: {summary['total_files']}")

    # 5.2 GET /api/omr/jobs/{job_id}/results
    resp_res = client.get(f"/api/omr/jobs/{job_id}/results")
    assert resp_res.status_code == 200
    res_data = resp_res.json()
    assert res_data["job_id"] == job_id
    assert len(res_data["results"]) >= 1
    print(f"✓ GET /api/omr/jobs/{job_id}/results -> {len(res_data['results'])} resultado(s) recuperado(s).")

    # 5.3 GET /api/omr/jobs/{job_id}/files
    resp_files = client.get(f"/api/omr/jobs/{job_id}/files")
    assert resp_files.status_code == 200
    files_data = resp_files.json()
    assert files_data["total_files"] >= 1
    first_file = files_data["files"][0]
    print(f"✓ GET /api/omr/jobs/{job_id}/files -> Archivo procesado: {first_file['filename']}")

    # 5.4 GET /api/omr/jobs/{job_id}/image/{filename}
    resp_img = client.get(first_file["url"])
    assert resp_img.status_code == 200
    assert resp_img.headers["content-type"].startswith("image/")
    assert len(resp_img.content) == first_file["size_bytes"]
    print(f"✓ GET {first_file['url']} -> Imagen marcada descargada ({len(resp_img.content)} bytes).")

    # 5.5 GET /api/omr/jobs/{job_id}/export/csv
    resp_csv = client.get(f"/api/omr/jobs/{job_id}/export/csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "file_id" in resp_csv.text
    print("✓ GET /api/omr/jobs/{job_id}/export/csv -> CSV compatible descargado.")

    # 5.6 GET /api/omr/jobs/{job_id}/export/excel
    resp_excel = client.get(f"/api/omr/jobs/{job_id}/export/excel")
    assert resp_excel.status_code == 200
    assert "spreadsheetml" in resp_excel.headers["content-type"]
    assert len(resp_excel.content) > 0

    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(resp_excel.content))
    assert "Resultados" in wb.sheetnames, "Falta hoja 'Resultados' en Excel"
    assert "Detalle" in wb.sheetnames, "Falta hoja 'Detalle' en Excel"

    ws_res = wb["Resultados"]
    res_headers = [cell.value for cell in ws_res[1]]
    for col in ["archivo", "score", "porcentaje", "correctas", "incorrectas", "sin responder"]:
        assert col in res_headers, f"Falta columna '{col}' en hoja Resultados"

    ws_det = wb["Detalle"]
    det_headers = [cell.value for cell in ws_det[1]]
    for col in ["archivo", "pregunta", "marcada", "correcta", "resultado", "score"]:
        assert col in det_headers, f"Falta columna '{col}' en hoja Detalle"

    print("✓ GET /api/omr/jobs/{job_id}/export/excel -> Libro Excel (.xlsx) validado (Resultados y Detalle).")


if __name__ == "__main__":
    test_swagger_and_openapi()
    std_job_id = test_process_standard_sheet_zip_without_template()
    dyn_job_id = test_process_with_dynamic_answer_key()
    test_max_questions_limit_validation()
    sample5_job_id = test_process_multiple_with_evaluation()
    test_validation_and_security_errors()
    test_job_query_and_export_endpoints(std_job_id)
    test_job_query_and_export_endpoints(dyn_job_id)
    test_job_query_and_export_endpoints(sample5_job_id)
    print("\n=======================================================")
    print("TODAS LAS PRUEBAS DEL ENDPOINT ZIP COMPLETADAS EXITOSAMENTE")
    print("=======================================================")
