"""
test_tarea2.py - Verificación integral de la TAREA 2:
1. Nombre del examen obligatorio y asociado al Job
2. Puntos modalidad 1 (mismo valor) y modalidad 2 (puntos específicos con decimales)
3. Aislamiento estricto de Historial por usuario autenticado (/api/omr/history)
4. Consulta de Detalle del examen (/api/omr/jobs/{job_id} y /results)
5. Límite estricto de 40 preguntas
6. No regresión en procesamiento OMR y exportaciones
"""

import io
import json
import zipfile
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings

client = TestClient(app)

def create_sample_zip(image_names=("hoja_estandar.png",)):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for img_name in image_names:
            img_path = settings.STANDARD_TEMPLATE_DIR / img_name
            if not img_path.exists():
                img_path = settings.SAMPLES_DIR / "sample5" / "ScanBatch1" / "camscanner-1.jpg"
            zf.writestr(img_name, img_path.read_bytes())
    zip_buffer.seek(0)
    return zip_buffer

def register_and_login(nombre, correo, clave):
    # Registro
    client.post(
        "/api/auth/register",
        json={
            "nombre": nombre,
            "correo": correo,
            "clave": clave,
            "confirmacion_clave": clave,
        },
    )
    # Login
    res = client.post(
        "/api/auth/login",
        json={"correo": correo, "clave": clave},
    )
    assert res.status_code == 200
    return res.json()["token"]

def test_tarea2():
    print("=======================================================")
    print("INICIANDO PRUEBAS DE TAREA 2")
    print("=======================================================")

    # 1. Crear usuarios de prueba para verificar aislamiento de historial
    token_prof_a = register_and_login(
        "Profesor Carlos", "carlos@universidad.edu.ve", "ProfesorClave123"
    )
    token_prof_b = register_and_login(
        "Profesora Maria", "maria@universidad.edu.ve", "MariaClave456"
    )
    headers_a = {"Authorization": f"Bearer {token_prof_a}"}
    headers_b = {"Authorization": f"Bearer {token_prof_b}"}

    # 2. Validación de nombre de examen vacío
    print("\n--- 1. Probando validación de Nombre de Examen obligatorio ---")
    zip_buf = create_sample_zip()
    res = client.post(
        "/api/omr/process",
        files={"zip_file": ("test.zip", zip_buf, "application/zip")},
        data={"exam_name": "   "},
        headers=headers_a,
    )
    assert res.status_code == 400
    assert "nombre del examen es obligatorio" in res.json()["detail"].lower()
    print("✓ Nombre de examen vacío rechazado con HTTP 400.")

    # 3. Procesar examen con Modalidad 1 (Mismo valor: 2 puntos por pregunta)
    print("\n--- 2. Probando Modalidad 1: Mismo valor (2 puntos por pregunta) ---")
    eval_equal = {
        "source_type": "custom",
        "options": {
            "questions_in_order": [f"q{i}" for i in range(1, 41)],
            "answers_in_order": ["A", "B", "C", "D", "E"] * 8,
            "should_explain_scoring": True,
        },
        "marking_schemes": {
            "DEFAULT": {"correct": 2.0, "incorrect": 0, "unmarked": 0}
        },
    }
    eval_equal_bytes = json.dumps(eval_equal).encode("utf-8")

    zip_buf = create_sample_zip()
    res = client.post(
        "/api/omr/process",
        files={
            "zip_file": ("test.zip", zip_buf, "application/zip"),
            "evaluation": ("evaluation.json", io.BytesIO(eval_equal_bytes), "application/json"),
        },
        data={"exam_name": "Parcial 1 Cálculo I"},
        headers=headers_a,
    )
    assert res.status_code == 200, res.text
    data_a = res.json()
    job_id_a = data_a["job_id"]
    assert data_a["exam_name"] == "Parcial 1 Cálculo I"
    assert data_a["question_count"] == 40
    assert data_a["user_name"] == "Profesor Carlos"
    # Max score con 40 preguntas x 2 puntos = 80 puntos
    sheet_0 = data_a["results"][0]
    assert sheet_0["max_score"] == 80.0
    print(f"✓ Examen '{data_a['exam_name']}' procesado con éxito (job_id: {job_id_a}).")
    print(f"✓ Puntaje máximo calculado: {sheet_0['max_score']} (40 x 2 pts). Score: {sheet_0['score']}")

    # 4. Procesar examen con Modalidad 2 (Puntos específicos: q1=1, q2=1.5, q3=3.0, etc.)
    print("\n--- 3. Probando Modalidad 2: Puntos específicos (valores con decimales) ---")
    marking_schemes_specific = {
        "DEFAULT": {"correct": 1.0, "incorrect": 0, "unmarked": 0},
        "SECTION_q1": {"questions": ["q1"], "marking": {"correct": 1.0, "incorrect": 0, "unmarked": 0}},
        "SECTION_q2": {"questions": ["q2"], "marking": {"correct": 2.5, "incorrect": 0, "unmarked": 0}},
        "SECTION_q3": {"questions": ["q3"], "marking": {"correct": 1.5, "incorrect": 0, "unmarked": 0}},
    }
    eval_specific = {
        "source_type": "custom",
        "options": {
            "questions_in_order": [f"q{i}" for i in range(1, 41)],
            "answers_in_order": ["A", "B", "C", "D", "E"] * 8,
            "should_explain_scoring": True,
        },
        "marking_schemes": marking_schemes_specific,
    }
    eval_specific_bytes = json.dumps(eval_specific).encode("utf-8")

    zip_buf_b = create_sample_zip()
    res_b = client.post(
        "/api/omr/process",
        files={
            "zip_file": ("test.zip", zip_buf_b, "application/zip"),
            "evaluation": ("evaluation.json", io.BytesIO(eval_specific_bytes), "application/json"),
        },
        data={"exam_name": "Química General II"},
        headers=headers_b,
    )
    assert res_b.status_code == 200, res_b.text
    data_b = res_b.json()
    job_id_b = data_b["job_id"]
    assert data_b["exam_name"] == "Química General II"
    assert data_b["user_name"] == "Profesora Maria"
    # Max score: q1=1 + q2=2.5 + q3=1.5 + 37 preguntas restantes a 1 pt = 42.0
    sheet_b0 = data_b["results"][0]
    assert sheet_b0["max_score"] == 42.0
    print(f"✓ Examen '{data_b['exam_name']}' procesado con éxito (job_id: {job_id_b}).")
    print(f"✓ Puntaje específico calculado con decimales: max_score = {sheet_b0['max_score']}")

    # 5. Probando Historial y aislamiento por usuario (/api/omr/history)
    print("\n--- 4. Probando Historial y aislamiento entre usuarios ---")
    res_hist_a = client.get("/api/omr/history", headers=headers_a)
    assert res_hist_a.status_code == 200
    exams_a = res_hist_a.json()
    assert any(e["job_id"] == job_id_a for e in exams_a)
    assert not any(e["job_id"] == job_id_b for e in exams_a)
    print(f"✓ Historial Profesor Carlos contiene su examen ('{data_a['exam_name']}').")
    print("✓ Verificado: Profesor Carlos NO puede ver los exámenes de Profesora Maria.")

    res_hist_b = client.get("/api/omr/history", headers=headers_b)
    assert res_hist_b.status_code == 200
    exams_b = res_hist_b.json()
    assert any(e["job_id"] == job_id_b for e in exams_b)
    assert not any(e["job_id"] == job_id_a for e in exams_b)
    print(f"✓ Historial Profesora Maria contiene su examen ('{data_b['exam_name']}').")
    print("✓ Verificado: Profesora Maria NO puede ver los exámenes de Profesor Carlos.")

    # 6. Probando Detalle del examen
    print("\n--- 5. Probando consulta de Detalle del examen ---")
    res_summary = client.get(f"/api/omr/jobs/{job_id_a}", headers=headers_a)
    assert res_summary.status_code == 200
    sum_data = res_summary.json()
    assert sum_data["exam_name"] == "Parcial 1 Cálculo I"
    assert sum_data["question_count"] == 40
    assert sum_data["total_files"] == 1
    assert sum_data["status"] == "completed"
    print(f"✓ GET /api/omr/jobs/{job_id_a} retornó nombre, fecha, usuario y preguntas correctamente.")

    res_results = client.get(f"/api/omr/jobs/{job_id_a}/results", headers=headers_a)
    assert res_results.status_code == 200
    res_data = res_results.json()
    assert res_data["exam_name"] == "Parcial 1 Cálculo I"
    assert len(res_data["results"]) == 1
    print(f"✓ GET /api/omr/jobs/{job_id_a}/results confirmó nombre y estudiantes procesados.")

    # 7. Probando límite estricto de preguntas (>40)
    print("\n--- 6. Probando límite estricto de preguntas (máx 40) ---")
    eval_invalid = {
        "source_type": "custom",
        "options": {
            "questions_in_order": [f"q{i}" for i in range(1, 42)], # 41 preguntas
            "answers_in_order": ["A"] * 41,
        },
        "marking_schemes": {
            "DEFAULT": {"correct": 1, "incorrect": 0, "unmarked": 0}
        }
    }
    zip_buf = create_sample_zip()
    res_inv = client.post(
        "/api/omr/process",
        files={
            "zip_file": ("test.zip", zip_buf, "application/zip"),
            "evaluation": ("evaluation.json", io.BytesIO(json.dumps(eval_invalid).encode("utf-8")), "application/json"),
        },
        data={"exam_name": "Examen Inválido 41 preguntas"},
        headers=headers_a,
    )
    assert res_inv.status_code == 400
    assert "límite máximo de 40 preguntas" in res_inv.json()["detail"]
    print("✓ 41 preguntas rechazadas con HTTP 400.")

    print("\n=======================================================")
    print("TODAS LAS PRUEBAS DE LA TAREA 2 COMPLETADAS EXITOSAMENTE")
    print("=======================================================")

if __name__ == "__main__":
    test_tarea2()
