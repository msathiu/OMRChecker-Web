"""
test_user_creation.py - Suite de pruebas automatizadas para la creación de usuarios y validación de errores.

Verifica los 10 puntos obligatorios:
1. Creación exitosa de un usuario desde la cuenta de administrador.
2. Envío correcto de todos los campos obligatorios.
3. Respuesta apropiada cuando falta un campo obligatorio.
4. Rechazo de un correo electrónico con formato inválido.
5. Tratamiento de un correo que ya está registrado.
6. Rechazo de solicitudes administrativas realizadas por usuarios sin permisos (403 Forbidden).
7. Manejo correcto de respuestas 422 sin mostrar únicamente 'Field required'.
8. Persistencia del usuario creado en la base de datos SQLite (omr_web.db).
9. Compatibilidad con el inicio de sesión del usuario recién creado (/api/auth/login).
10. Ausencia de regresiones en registro, inicio de sesión, roles existentes y prevención de admin vía API.
"""

import sqlite3
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Aplicar parche headless antes de módulos de visión
import backend.app.core.headless_patch  # noqa: F401

from starlette.testclient import TestClient
from backend.app.core.config import settings
from backend.app.db.database import get_db, get_db_path
from backend.app.main import app
from backend.app.services.auth_service import auth_service

client = TestClient(app)


def get_or_create_admin() -> tuple[str, str]:
    """Retorna (token, email) de un administrador para pruebas."""
    admin_email = "admin_test@omrchecker.local"
    admin_pass = "AdminPass123*"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE correo = ? COLLATE NOCASE;", (admin_email,))
        row = cursor.fetchone()
        if not row:
            admin_id = str(uuid.uuid4())
            pwd_hash = auth_service._hash_password(admin_pass)
            cursor.execute(
                """
                INSERT INTO users (id, nombre, correo, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, 'Admin Test', ?, ?, 'admin', 1, datetime('now'), datetime('now'));
                """,
                (admin_id, admin_email, pwd_hash),
            )
            auth_service._sync_json_files()

    # Login como admin
    res = client.post("/api/auth/login", json={"correo": admin_email, "clave": admin_pass})
    assert res.status_code == 200, f"Error en login admin: {res.text}"
    return res.json()["token"], admin_email


def get_or_create_regular_user() -> tuple[str, str]:
    """Retorna (token, email) de un usuario normal (rol usuario)."""
    user_email = f"user_{uuid.uuid4().hex[:6]}@omrchecker.local"
    user_pass = "UserPass123*"

    # Registro
    res = client.post(
        "/api/auth/register",
        json={
            "nombre": "Usuario Regular",
            "correo": user_email,
            "clave": user_pass,
            "confirmacion_clave": user_pass,
        },
    )
    assert res.status_code == 201

    res_login = client.post("/api/auth/login", json={"correo": user_email, "clave": user_pass})
    assert res_login.status_code == 200
    return res_login.json()["token"], user_email


def test_suite_user_creation():
    print("\n=======================================================")
    print("INICIANDO SUITE DE PRUEBAS DE CREACIÓN DE USUARIOS")
    print("=======================================================")

    admin_token, admin_email = get_or_create_admin()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # -------------------------------------------------------------
    # 1 & 2: Creación exitosa y envío correcto de todos los campos
    # -------------------------------------------------------------
    print("\n--- 1 & 2. Creación exitosa de usuario por administrador con campos obligatorios ---")
    new_user_email = f"profesor_{uuid.uuid4().hex[:6]}@institucion.edu"
    payload_valid = {
        "nombre": "Profesor Evaluador Uno",
        "correo": new_user_email,
        "clave": "Temporal2026*",
        "role": "editor",
    }
    res_create = client.post("/api/users", json=payload_valid, headers=admin_headers)
    assert res_create.status_code == 201, f"Fallo al crear usuario: {res_create.status_code} {res_create.text}"
    data_created = res_create.json()
    assert data_created["nombre"] == "Profesor Evaluador Uno"
    assert data_created["correo"] == new_user_email
    assert data_created["role"] == "editor"
    assert "clave" not in data_created
    assert "password_hash" not in data_created
    print(f"✓ Usuario creado exitosamente con rol editor: {new_user_email}")

    # Creación de usuario con confirmacion_clave opcional enviada
    new_user_email_2 = f"alumno_{uuid.uuid4().hex[:6]}@institucion.edu"
    payload_valid_2 = {
        "nombre": "Estudiante Evaluado Dos",
        "correo": new_user_email_2,
        "clave": "Temporal2026*",
        "confirmacion_clave": "Temporal2026*",
        "role": "usuario",
    }
    res_create_2 = client.post("/api/users", json=payload_valid_2, headers=admin_headers)
    assert res_create_2.status_code == 201
    print(f"✓ Usuario creado exitosamente con confirmación coincidente y rol usuario: {new_user_email_2}")

    # -------------------------------------------------------------
    # 3: Respuesta apropiada cuando falta un campo obligatorio
    # -------------------------------------------------------------
    print("\n--- 3. Respuesta apropiada cuando falta un campo obligatorio ---")
    # Falta nombre
    res_no_nombre = client.post(
        "/api/users",
        json={"correo": "sin_nombre@institucion.edu", "clave": "Clave123*", "role": "editor"},
        headers=admin_headers,
    )
    assert res_no_nombre.status_code == 422
    err_body = res_no_nombre.json()
    assert any("nombre" in str(e.get("loc", [])) for e in err_body.get("detail", []))
    print("✓ Falta 'nombre' genera 422 identificando el campo.")

    # Falta correo
    res_no_mail = client.post(
        "/api/users",
        json={"nombre": "Sin Correo", "clave": "Clave123*", "role": "editor"},
        headers=admin_headers,
    )
    assert res_no_mail.status_code == 422
    err_body = res_no_mail.json()
    assert any("correo" in str(e.get("loc", [])) for e in err_body.get("detail", []))
    print("✓ Falta 'correo' genera 422 identificando el campo.")

    # Falta clave
    res_no_clave = client.post(
        "/api/users",
        json={"nombre": "Sin Clave", "correo": "sin_clave@institucion.edu", "role": "editor"},
        headers=admin_headers,
    )
    assert res_no_clave.status_code == 422
    err_body = res_no_clave.json()
    assert any("clave" in str(e.get("loc", [])) for e in err_body.get("detail", []))
    print("✓ Falta 'clave' genera 422 identificando el campo.")

    # -------------------------------------------------------------
    # 4: Rechazo de un correo electrónico con formato inválido
    # -------------------------------------------------------------
    print("\n--- 4. Rechazo de correo electrónico con formato inválido ---")
    res_invalid_email = client.post(
        "/api/users",
        json={"nombre": "Correo Invalido", "correo": "invalido-sin-arroba", "clave": "Clave123*", "role": "usuario"},
        headers=admin_headers,
    )
    assert res_invalid_email.status_code == 422
    assert "correo" in str(res_invalid_email.json()).lower()
    print("✓ Correo con formato inválido rechazado con 422.")

    # -------------------------------------------------------------
    # 5: Tratamiento de un correo que ya está registrado
    # -------------------------------------------------------------
    print("\n--- 5. Tratamiento de un correo que ya está registrado ---")
    res_duplicate = client.post(
        "/api/users",
        json={"nombre": "Duplicado Intento", "correo": new_user_email, "clave": "OtraClave123*", "role": "editor"},
        headers=admin_headers,
    )
    assert res_duplicate.status_code == 400
    assert "ya existe un usuario" in res_duplicate.json().get("detail", "").lower()
    print("✓ Correo duplicado rechazado controladamente con HTTP 400 y mensaje en español.")

    # -------------------------------------------------------------
    # 6: Rechazo de solicitudes administrativas por usuarios sin permisos
    # -------------------------------------------------------------
    print("\n--- 6. Rechazo de solicitudes administrativas sin permisos (401 / 403) ---")
    # Sin autenticación
    res_no_auth = client.post("/api/users", json=payload_valid)
    assert res_no_auth.status_code == 401
    print("✓ Solicitud sin token rechazada con 401 Unauthorized.")

    # Con usuario de rol normal (no admin)
    regular_token, _ = get_or_create_regular_user()
    res_forbidden = client.post(
        "/api/users",
        json=payload_valid,
        headers={"Authorization": f"Bearer {regular_token}"},
    )
    assert res_forbidden.status_code == 403
    assert "acceso denegado" in res_forbidden.json().get("detail", "").lower()
    print("✓ Solicitud de usuario no-admin rechazada con 403 Forbidden.")

    # -------------------------------------------------------------
    # 7: Manejo de respuestas 422 sin mostrar únicamente 'Field required'
    # -------------------------------------------------------------
    print("\n--- 7. Respuestas 422 con formato comprensible en español (sin 'Field required' genérico) ---")
    res_missing = client.post("/api/users", json={}, headers=admin_headers)
    assert res_missing.status_code == 422
    data_422 = res_missing.json()
    # Verificar que el mensaje devuelto no sea simplemente el string crudo en inglés
    detail_items = data_422.get("detail", [])
    for item in detail_items:
        msg = item.get("msg", "")
        assert "Field required" not in msg, f"Mensaje no traducido detectado: {msg}"
        assert "es obligatorio" in msg or "obligatorio" in msg, f"Mensaje amigable esperado, obtenido: {msg}"
    assert "message" in data_422
    assert "es obligatorio" in data_422["message"]
    print("✓ Errores 422 formateados en español claro con nombres de campo explicados.")

    # -------------------------------------------------------------
    # 8: Persistencia del usuario creado en la base de datos SQLite
    # -------------------------------------------------------------
    print("\n--- 8. Persistencia y seguridad en SQLite (omr_web.db) ---")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, correo, password_hash, role, is_active FROM users WHERE correo = ?;", (new_user_email,))
        row = cursor.fetchone()
        assert row is not None, "El usuario no fue persistido en la tabla users de SQLite."
        assert row["nombre"] == "Profesor Evaluador Uno"
        assert row["role"] == "editor"
        assert row["is_active"] == 1
        # Comprobar que la contraseña NO está en texto plano
        pwd_hash = row["password_hash"]
        assert pwd_hash != "Temporal2026*"
        assert "$" in pwd_hash
    print("✓ Persistencia en SQLite confirmada y contraseña almacenada con hash seguro con salt.")

    # -------------------------------------------------------------
    # 9: Compatibilidad con el inicio de sesión del usuario recién creado
    # -------------------------------------------------------------
    print("\n--- 9. Inicio de sesión del usuario recién creado ---")
    res_login_new = client.post(
        "/api/auth/login",
        json={"correo": new_user_email, "clave": "Temporal2026*"},
    )
    assert res_login_new.status_code == 200, f"No se pudo iniciar sesión con usuario creado: {res_login_new.text}"
    token_new = res_login_new.json()["token"]
    assert token_new is not None

    # Verificar que puede consultar su perfil
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_new}"})
    assert res_me.status_code == 200
    assert res_me.json()["correo"] == new_user_email
    assert res_me.json()["role"] == "editor"
    print("✓ El nuevo usuario inició sesión inmediatamente y obtuvo su perfil autenticado.")

    # -------------------------------------------------------------
    # 10: No regresiones en el sistema existente
    # -------------------------------------------------------------
    print("\n--- 10. Verificación de no regresión en roles, admin CLI y operaciones ---")
    # 10.1 Prohibido crear rol admin por API
    res_admin_attempt = client.post(
        "/api/users",
        json={"nombre": "Hacker Admin", "correo": "hacker@test.local", "clave": "Clave123*", "role": "admin"},
        headers=admin_headers,
    )
    assert res_admin_attempt.status_code in (400, 422)
    assert "administrador" in str(res_admin_attempt.text).lower()
    print("✓ Intento de crear rol 'admin' por API bloqueado estrictamente.")

    # 10.2 Listado de usuarios por admin
    res_list = client.get("/api/users", headers=admin_headers)
    assert res_list.status_code == 200
    user_list = res_list.json()
    assert isinstance(user_list, list)
    assert any(u["correo"] == new_user_email for u in user_list)
    print("✓ Listado de usuarios funcionando con el nuevo usuario incluido.")

    # 10.3 Modificación de usuario (PUT /api/users/{id})
    res_update = client.put(
        f"/api/users/{data_created['id']}",
        json={"nombre": "Profesor Evaluador Modificado"},
        headers=admin_headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["nombre"] == "Profesor Evaluador Modificado"
    print("✓ Actualización de usuario por administrador funcionando.")

    # 10.4 Eliminación de usuario (DELETE /api/users/{id})
    res_del = client.delete(f"/api/users/{data_created['id']}", headers=admin_headers)
    assert res_del.status_code == 200
    print("✓ Eliminación de usuario funcionando correctamente.")

    print("\n=======================================================")
    print("¡TODAS LAS 10 PRUEBAS OBLIGATORIAS PASARON EXITOSAMENTE!")
    print("=======================================================\n")


if __name__ == "__main__":
    test_suite_user_creation()
