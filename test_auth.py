"""
test_auth.py - Suite de pruebas automatizadas para Registro, Inicio y Cierre de Sesión.

Verifica:
1. Registro válido              → OK (201)
2. Registro con correo repetido → ERROR controlado (400)
3. Claves diferentes            → ERROR controlado (422)
4. Campos vacíos                → ERROR controlado (422)
5. Login válido                 → OK (200)
6. Login inválido               → ERROR controlado (401)
7. Sesión (/api/auth/me)        → OK (200)
8. Cerrar sesión                → OK (200) e invalidación de token
9. Acceso sin sesión            → BLOQUEADO (401)
10. Persistencia y no texto plano en storage/users/users.json
"""

import json
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.core.config import settings
from backend.app.main import app

client = TestClient(app)


def test_authentication_suite():
    print("\n=======================================================")
    print("INICIANDO PRUEBAS DE AUTENTICACIÓN (TAREA 1)")
    print("=======================================================")

    # Limpiar storage de prueba para pruebas limpias
    if settings.USERS_FILE.exists():
        settings.USERS_FILE.unlink()
    if settings.SESSIONS_FILE.exists():
        settings.SESSIONS_FILE.unlink()

    # 1. Campos vacíos
    print("\n--- 1. Probando validación de campos vacíos ---")
    resp_empty = client.post("/api/auth/register", json={
        "nombre": "",
        "correo": "usuario@institucion.edu",
        "clave": "secreta123",
        "confirmacion_clave": "secreta123",
    })
    assert resp_empty.status_code == 422, f"Esperado 422, obtenido {resp_empty.status_code}"
    print("✓ Nombre vacío rechazado con HTTP 422.")

    resp_empty_mail = client.post("/api/auth/register", json={
        "nombre": "Profesor Ejemplo",
        "correo": "",
        "clave": "secreta123",
        "confirmacion_clave": "secreta123",
    })
    assert resp_empty_mail.status_code == 422
    print("✓ Correo vacío rechazado con HTTP 422.")

    # 2. Formato de correo inválido
    print("\n--- 2. Probando validación de formato de correo ---")
    resp_bad_mail = client.post("/api/auth/register", json={
        "nombre": "Profesor Ejemplo",
        "correo": "correo_invalido_sin_arroba",
        "clave": "secreta123",
        "confirmacion_clave": "secreta123",
    })
    assert resp_bad_mail.status_code == 422
    print("✓ Correo mal formateado rechazado con HTTP 422.")

    # 3. Claves diferentes
    print("\n--- 3. Probando validación de claves no coincidentes ---")
    resp_diff_pwd = client.post("/api/auth/register", json={
        "nombre": "Profesor Ejemplo",
        "correo": "profesor@institucion.edu",
        "clave": "clave123",
        "confirmacion_clave": "otra_clave_distinta",
    })
    assert resp_diff_pwd.status_code == 422
    print("✓ Claves diferentes rechazadas con HTTP 422.")

    # 4. Registro válido
    print("\n--- 4. Probando registro válido ---")
    valid_payload = {
        "nombre": "Profesor Juan Pérez",
        "correo": "juan.perez@institucion.edu",
        "clave": "Segura2026*",
        "confirmacion_clave": "Segura2026*",
    }
    resp_reg = client.post("/api/auth/register", json=valid_payload)
    assert resp_reg.status_code == 201, f"Esperado 201, obtenido {resp_reg.status_code}: {resp_reg.text}"
    user_data = resp_reg.json()
    assert user_data["nombre"] == "Profesor Juan Pérez"
    assert user_data["correo"] == "juan.perez@institucion.edu"
    assert "id" in user_data
    assert "clave" not in user_data
    assert "password_hash" not in user_data
    print(f"✓ Usuario registrado exitosamente (id: {user_data['id']}).")

    # 4.1 Verificar que la clave NO está en texto plano en disco
    assert settings.USERS_FILE.exists()
    with settings.USERS_FILE.open("r", encoding="utf-8") as f:
        stored_users = json.load(f)
    stored_user = stored_users[user_data["id"]]
    assert stored_user["password_hash"] != "Segura2026*"
    assert "$" in stored_user["password_hash"]
    print("✓ Verificado: La clave está hasheada con salt en almacenamiento persistente.")

    # 5. Registro con correo repetido
    print("\n--- 5. Probando rechazo de correo duplicado ---")
    resp_dup = client.post("/api/auth/register", json=valid_payload)
    assert resp_dup.status_code == 400, f"Esperado 400, obtenido {resp_dup.status_code}"
    assert "ya existe" in resp_dup.json()["detail"].lower()
    print("✓ Correo duplicado rechazado controladamente con HTTP 400.")

    # 6. Login inválido
    print("\n--- 6. Probando login inválido (credenciales erróneas) ---")
    resp_bad_login = client.post("/api/auth/login", json={
        "correo": "juan.perez@institucion.edu",
        "clave": "clave_equivocada",
    })
    assert resp_bad_login.status_code == 401, f"Esperado 401, obtenido {resp_bad_login.status_code}"
    assert "credenciales incorrectas" in resp_bad_login.json()["detail"].lower()
    print("✓ Login con clave incorrecta rechazado con HTTP 401 sin revelar detalles.")

    resp_bad_user = client.post("/api/auth/login", json={
        "correo": "no_existe@institucion.edu",
        "clave": "Segura2026*",
    })
    assert resp_bad_user.status_code == 401
    print("✓ Login con correo inexistente rechazado con HTTP 401 de forma segura.")

    # 7. Login válido
    print("\n--- 7. Probando login válido ---")
    resp_login = client.post("/api/auth/login", json={
        "correo": "juan.perez@institucion.edu",
        "clave": "Segura2026*",
    })
    assert resp_login.status_code == 200, f"Esperado 200, obtenido {resp_login.status_code}"
    login_data = resp_login.json()
    assert "token" in login_data
    token = login_data["token"]
    assert login_data["user"]["correo"] == "juan.perez@institucion.edu"
    print(f"✓ Login exitoso. Token generado.")

    # 8. Sesión (/api/auth/me) con token válido
    print("\n--- 8. Probando consulta de sesión activa (/api/auth/me) ---")
    resp_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200
    assert resp_me.json()["id"] == user_data["id"]
    print(f"✓ Sesión validada correctamente para {resp_me.json()['nombre']}.")

    # 9. Acceso sin sesión
    print("\n--- 9. Probando acceso sin sesión (/api/auth/me sin token) ---")
    resp_no_auth = client.get("/api/auth/me")
    assert resp_no_auth.status_code == 401
    print("✓ Acceso sin token bloqueado con HTTP 401.")

    # 10. Cerrar sesión
    print("\n--- 10. Probando cierre de sesión (/api/auth/logout) ---")
    resp_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp_logout.status_code == 200
    print("✓ Endpoint logout respondió HTTP 200.")

    # 10.1 Verificar que el token quedó invalidado
    resp_me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me_after.status_code == 401, f"Token no fue invalidado: {resp_me_after.status_code}"
    print("✓ Verificado: El token fue revocado y ya no permite acceder a endpoints protegidos.")

    print("\n=======================================================")
    print("TODAS LAS PRUEBAS DE AUTENTICACIÓN PASARON EXITOSAMENTE")
    print("=======================================================")


if __name__ == "__main__":
    test_authentication_suite()
