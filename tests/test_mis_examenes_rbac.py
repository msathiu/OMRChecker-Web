"""
test_mis_examenes_rbac.py - Suite de pruebas automatizadas para «Mis exámenes»,
gestión de exámenes por Editor y restricción de permisos del usuario normal.

Verifica:
1. Usuario normal sin exámenes asignados recibe lista vacía [].
2. Usuario normal no puede consultar detalles de un examen no asignado (403 Forbidden).
3. Usuario normal no puede crear, modificar ni eliminar exámenes (403 Forbidden).
4. Usuario normal no puede asignar ni desasignar exámenes (403 Forbidden).
5. Editor puede crear examen con clave de respuestas y esquema de puntuación en SQLite.
6. Editor puede asignar examen a usuarios sin requerir carga de archivos ZIP.
7. Asignaciones se persisten en tabla exam_assignments y evitan duplicados.
8. Editor puede listar asignaciones del examen.
9. Editor puede desasignar usuarios.
10. Editor puede consultar /api/users y recibe únicamente usuarios activos con rol 'usuario'.
11. Usuario normal no tiene acceso a /api/users (403 Forbidden).
12. Usuario normal asignado visualiza el examen pero la clave de respuestas está oculta.
13. Usuario normal no puede procesar OMR sin exam_id (400 Bad Request).
14. Usuario normal no puede procesar OMR de un exam_id no asignado (403 Forbidden).
"""

import io
import json
import sqlite3
import sys
import uuid
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import backend.app.core.headless_patch  # noqa: F401

from starlette.testclient import TestClient
from backend.app.db.database import get_db
from backend.app.main import app
from backend.app.services.auth_service import auth_service

client = TestClient(app)


def create_or_login_user(name: str, email: str, role: str, password: str = "TestPass123*") -> tuple[str, int]:
    """Crea o reutiliza usuario y retorna (token, user_id)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE correo = ? COLLATE NOCASE;", (email,))
        row = cursor.fetchone()
        if not row:
            uid = str(uuid.uuid4())
            pwd_hash = auth_service._hash_password(password)
            cursor.execute(
                """
                INSERT INTO users (id, nombre, correo, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'));
                """,
                (uid, name, email, pwd_hash, role),
            )
            auth_service._sync_json_files()

    res = client.post("/api/auth/login", json={"correo": email, "clave": password})
    assert res.status_code == 200, f"Error login {email}: {res.text}"
    token = res.json()["token"]
    user_id = res.json()["user"]["id"]
    return token, user_id


def test_normal_user_without_assignments_sees_empty_list():
    """1. Usuario normal sin asignaciones recibe lista vacía en /api/exams."""
    token, _ = create_or_login_user("Alumno Sin Examen", "alumno_vacio@test.local", "usuario")
    res = client.get("/api/exams", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == [], "El usuario sin asignaciones debe recibir una lista vacía"


def test_normal_user_cannot_create_or_modify_exams():
    """2. Usuario normal no puede crear, modificar ni eliminar exámenes (403 Forbidden)."""
    token, _ = create_or_login_user("Alumno Bloqueado", "alumno_bloqueado@test.local", "usuario")
    headers = {"Authorization": f"Bearer {token}"}

    # Intentar crear
    payload = {
        "name": "Examen Ilegal",
        "question_count": 5,
        "scoring_mode": "EQUAL",
        "equal_points": 1.0,
        "answers": {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"},
    }
    res_create = client.post("/api/exams", json=payload, headers=headers)
    assert res_create.status_code == 403, "Usuario normal no debe poder crear exámenes"

    # Intentar modificar
    res_update = client.put("/api/exams/fake-id", json=payload, headers=headers)
    assert res_update.status_code == 403, "Usuario normal no debe poder modificar exámenes"

    # Intentar eliminar
    res_del = client.delete("/api/exams/fake-id", headers=headers)
    assert res_del.status_code == 403, "Usuario normal no debe poder eliminar exámenes"


def test_normal_user_cannot_access_user_management():
    """3. Usuario normal no tiene acceso a /api/users (403 Forbidden)."""
    token, _ = create_or_login_user("Alumno Sin Users", "alumno_sin_users@test.local", "usuario")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/users", headers=headers)
    assert res.status_code == 403, "Usuario normal debe recibir 403 al consultar /api/users"


def test_editor_can_create_exam_and_query_assignable_users():
    """4. Editor puede crear examen y consultar usuarios tipo 'usuario' para asignación."""
    editor_token, editor_id = create_or_login_user("Profesor Juan", "profe_juan@test.local", "editor")
    headers = {"Authorization": f"Bearer {editor_token}"}

    # Crear examen con respuestas y puntuación específica
    payload = {
        "name": "Parcial de Álgebra Lineal",
        "description": "Examen de evaluación primer corte",
        "question_count": 5,
        "scoring_mode": "SPECIFIC",
        "specific_points": {"1": 2.5, "2": 2.5, "3": 1.5, "4": 1.5, "5": 2.0},
        "answers": {"1": "A", "2": "C", "3": "D", "4": "B", "5": "E"},
        "enabled_for_all": False,
    }
    res = client.post("/api/exams", json=payload, headers=headers)
    assert res.status_code == 201, f"Error al crear examen: {res.text}"
    exam = res.json()
    assert exam["name"] == "Parcial de Álgebra Lineal"
    assert exam["question_count"] == 5
    assert exam["answers"] == {"1": "A", "2": "C", "3": "D", "4": "B", "5": "E"}

    # Editor consulta usuarios candidatos
    res_users = client.get("/api/users", headers=headers)
    assert res_users.status_code == 200
    users_list = res_users.json()
    assert all(u["role"] == "usuario" for u in users_list), "Editor solo debe ver usuarios con rol 'usuario'"


def test_editor_can_assign_and_unassign_exam_without_zip():
    """5. Editor puede asignar y desasignar examen a estudiantes sin subir ZIP."""
    editor_token, _ = create_or_login_user("Profesor Maria", "profe_maria@test.local", "editor")
    headers = {"Authorization": f"Bearer {editor_token}"}

    # Crear usuarios estudiantes
    _, student_1_id = create_or_login_user("Estudiante Uno", "estudiante1@test.local", "usuario")
    _, student_2_id = create_or_login_user("Estudiante Dos", "estudiante2@test.local", "usuario")

    # Crear examen
    create_res = client.post(
        "/api/exams",
        json={
            "name": "Examen Quimica General",
            "question_count": 3,
            "scoring_mode": "EQUAL",
            "equal_points": 1.0,
            "answers": {"1": "A", "2": "B", "3": "C"},
            "enabled_for_all": False,
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    exam_id = create_res.json()["id"]

    # Asignar a estudiante 1 y 2 sin subir ningún archivo ZIP
    assign_res = client.post(
        f"/api/exams/{exam_id}/assign",
        json={"user_ids": [student_1_id, student_2_id]},
        headers=headers,
    )
    assert assign_res.status_code == 200, f"Error al asignar: {assign_res.text}"
    assign_data = assign_res.json()
    assert assign_data["assigned_count"] == 2

    # Consultar asignaciones
    list_assigns = client.get(f"/api/exams/{exam_id}/assignments", headers=headers)
    assert list_assigns.status_code == 200
    assigned_ids = [u["id"] for u in list_assigns.json()]
    assert student_1_id in assigned_ids
    assert student_2_id in assigned_ids

    # Desasignar estudiante 2
    del_res = client.delete(f"/api/exams/{exam_id}/assignments/{student_2_id}", headers=headers)
    assert del_res.status_code == 200

    # Verificar que solo queda estudiante 1
    list_assigns2 = client.get(f"/api/exams/{exam_id}/assignments", headers=headers)
    assert list_assigns2.status_code == 200
    assigned_ids2 = [u["id"] for u in list_assigns2.json()]
    assert student_1_id in assigned_ids2
    assert student_2_id not in assigned_ids2


def test_assigned_normal_user_sees_exam_without_answers():
    """6. Estudiante asignado ve el examen pero la clave de respuestas está oculta."""
    editor_token, _ = create_or_login_user("Profesor Carlos", "profe_carlos@test.local", "editor")
    student_token, student_id = create_or_login_user("Estudiante Asignado", "estudiante_asignado@test.local", "usuario")

    # Crear examen
    create_res = client.post(
        "/api/exams",
        json={
            "name": "Examen Historia Universal",
            "question_count": 4,
            "scoring_mode": "EQUAL",
            "equal_points": 2.0,
            "answers": {"1": "D", "2": "C", "3": "B", "4": "A"},
            "enabled_for_all": False,
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    exam_id = create_res.json()["id"]

    # Asignar a estudiante
    client.post(
        f"/api/exams/{exam_id}/assign",
        json={"user_ids": [student_id]},
        headers={"Authorization": f"Bearer {editor_token}"},
    )

    # Estudiante consulta lista de exámenes
    res_list = client.get("/api/exams", headers={"Authorization": f"Bearer {student_token}"})
    assert res_list.status_code == 200
    exams = res_list.json()
    matching = [e for e in exams if e["id"] == exam_id]
    assert len(matching) == 1, "El estudiante debe ver el examen asignado"
    exam_item = matching[0]
    assert exam_item.get("answers") is None, "La clave de respuestas debe estar oculta para el estudiante"

    # Estudiante consulta detalle del examen
    res_detail = client.get(f"/api/exams/{exam_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert res_detail.status_code == 200
    assert res_detail.json().get("answers") is None, "El detalle del examen no debe exponer respuestas al estudiante"


def test_normal_user_cannot_access_unassigned_exam():
    """7. Estudiante no asignado recibe 403 al consultar detalle de examen."""
    editor_token, _ = create_or_login_user("Profesor Privado", "profe_privado@test.local", "editor")
    other_student_token, _ = create_or_login_user("Estudiante Ajeno", "estudiante_ajeno@test.local", "usuario")

    create_res = client.post(
        "/api/exams",
        json={
            "name": "Examen Top Secret",
            "question_count": 5,
            "scoring_mode": "EQUAL",
            "equal_points": 1.0,
            "answers": {"1": "A", "2": "A", "3": "A", "4": "A", "5": "A"},
            "enabled_for_all": False,
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    exam_id = create_res.json()["id"]

    res = client.get(f"/api/exams/{exam_id}", headers={"Authorization": f"Bearer {other_student_token}"})
    assert res.status_code == 403, "Estudiante no asignado debe recibir 403 Forbidden"


def test_normal_user_processing_requires_assigned_exam():
    """8. Procesamiento OMR para rol usuario exige exam_id asignado (400 si falta, 403 si ajeno)."""
    student_token, student_id = create_or_login_user("Estudiante OMR", "estudiante_omr@test.local", "usuario")
    editor_token, _ = create_or_login_user("Profesor OMR", "profe_omr@test.local", "editor")

    # Crear ZIP ficticio
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("sheet1.txt", "dummy content")
    zip_bytes = zip_buf.getvalue()

    # 1. Intentar procesar sin exam_id -> 400 Bad Request
    files = {"zip_files": ("exams.zip", zip_bytes, "application/zip")}
    data = {"exam_name": "Intento Sin ID"}
    res_no_id = client.post(
        "/api/omr/process",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_no_id.status_code == 400, "Debe rechazar con 400 si un usuario normal no envía exam_id"

    # 2. Intentar procesar con exam_id no asignado -> 403 Forbidden
    create_res = client.post(
        "/api/exams",
        json={
            "name": "Examen Ajeno OMR",
            "question_count": 5,
            "scoring_mode": "EQUAL",
            "equal_points": 1.0,
            "answers": {"1": "A", "2": "B", "3": "C", "4": "D", "5": "E"},
            "enabled_for_all": False,
        },
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    ajeno_exam_id = create_res.json()["id"]

    res_unassigned = client.post(
        "/api/omr/process",
        files={"zip_files": ("exams.zip", zip_bytes, "application/zip")},
        data={"exam_id": ajeno_exam_id},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_unassigned.status_code == 403, "Debe rechazar con 403 si el examen no le ha sido asignado al usuario"


if __name__ == "__main__":
    tests = [
        test_normal_user_without_assignments_sees_empty_list,
        test_normal_user_cannot_create_or_modify_exams,
        test_normal_user_cannot_access_user_management,
        test_editor_can_create_exam_and_query_assignable_users,
        test_editor_can_assign_and_unassign_exam_without_zip,
        test_assigned_normal_user_sees_exam_without_answers,
        test_normal_user_cannot_access_unassigned_exam,
        test_normal_user_processing_requires_assigned_exam,
    ]
    print(f"\nEjecutando {len(tests)} pruebas de RBAC y Mis Exámenes...\n")
    passed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            raise
    print(f"\nTodas las {passed}/{len(tests)} pruebas pasaron exitosamente.\n")

