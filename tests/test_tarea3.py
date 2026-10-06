"""
test_tarea3.py - Suite completa de verificación para la TAREA 3 de OMRChecker.
Verifica:
1. Historial de exámenes (/api/omr/history, /api/history, /api/exams) sin errores 404.
2. Validación de correos institucionales en registro y login.
3. Manejo de errores OMR (hojas retenidas con status='ERROR', causa explicativa e imagen original).
4. Reintento selectivo con ZIP corregido (/api/omr/jobs/{job_id}/retry) sin duplicar hojas correctas.
5. Exportaciones CSV y Excel con columnas dinámicas q1..qN, cabeceras exactas y paridad total.
"""

import io
import json
import zipfile
import shutil
import tempfile
from pathlib import Path
import httpx
import pandas as pd
import openpyxl

BASE_URL = "http://localhost:8000"

def run_tests():
    print("=" * 60)
    print("INICIANDO PRUEBAS AUTOMATIZADAS - TAREA 3")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    # ---------------------------------------------------------
    # 1. VERIFICACIÓN DE ENDPOINTS DE HISTORIAL
    # ---------------------------------------------------------
    print("\n[1] Verificando endpoints de historial...")
    for endpoint in ["/api/omr/history", "/api/history", "/api/exams"]:
        res = client.get(endpoint)
        assert res.status_code == 200, f"Fallo en {endpoint}: HTTP {res.status_code}"
        data = res.json()
        assert isinstance(data, list), f"Se esperaba lista en {endpoint}"
        print(f"  ✓ {endpoint} responde HTTP 200 con {len(data)} exámenes registrados.")
        if len(data) > 0:
            first = data[0]
            for field in ["job_id", "exam_name", "status"]:
                assert field in first, f"Falta campo {field} en historial"

    # ---------------------------------------------------------
    # 2. VALIDACIÓN DE CORREO EN EL REGISTRO
    # ---------------------------------------------------------
    print("\n[2] Verificando validaciones de correo en registro...")
    # Correo inválido: 'maeva'
    res_inv1 = client.post("/api/auth/register", json={
        "nombre": "Maeva Test",
        "correo": "maeva",
        "clave": "Secreto123*",
        "confirmacion_clave": "Secreto123*"
    })
    assert res_inv1.status_code == 422, f"Esperado 422 para 'maeva', recibido {res_inv1.status_code}"
    print("  ✓ Correo sin formato ('maeva') rechazado correctamente con 422.")

    # Correo inválido: 'maeva@'
    res_inv2 = client.post("/api/auth/register", json={
        "nombre": "Maeva Test",
        "correo": "maeva@",
        "clave": "Secreto123*",
        "confirmacion_clave": "Secreto123*"
    })
    assert res_inv2.status_code == 422, f"Esperado 422 para 'maeva@', recibido {res_inv2.status_code}"
    print("  ✓ Correo incompleto ('maeva@') rechazado correctamente con 422.")

    # Correo institucional válido
    test_email = "profesor_tarea3@cenditel.gob.ve"
    res_reg = client.post("/api/auth/register", json={
        "nombre": "Profesor Tarea 3",
        "correo": test_email,
        "clave": "Docente2026*",
        "confirmacion_clave": "Docente2026*"
    })
    # Puede ser 201 (creado), 200 o 400 (ya existía de una corrida previa)
    assert res_reg.status_code in [200, 201, 400], f"Error inesperado en registro: {res_reg.text}"
    print(f"  ✓ Registro con correo institucional válido ('{test_email}') verificado (HTTP {res_reg.status_code}).")

    # Login
    res_login = client.post("/api/auth/login", json={
        "correo": test_email,
        "clave": "Docente2026*"
    })
    assert res_login.status_code == 200, f"Error en login: {res_login.text}"
    token = res_login.json()["token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    print("  ✓ Inicio de sesión exitoso y token Bearer obtenido.")

    # ---------------------------------------------------------
    # 3. PROCESAMIENTO CON HOJA ERRÓNEA Y HOJAS VÁLIDAS
    # ---------------------------------------------------------
    print("\n[3] Preparando lote OMR con hojas correctas y 1 hoja con error...")
    sample_dir = Path("samples/standard")
    hoja_std = sample_dir / "hoja_estandar.png"
    marker = sample_dir / "omr_marker.jpg"
    template_path = sample_dir / "template.json"
    eval_path = sample_dir / "evaluation.json"

    assert hoja_std.exists(), f"No se encontró {hoja_std}"
    assert template_path.exists(), f"No se encontró {template_path}"

    with open(template_path, "r") as f:
        template_obj = json.load(f)
    with open(eval_path, "r") as f:
        eval_obj = json.load(f)

    # Crear una imagen deliberadamente dañada/inválida para OMR (sin marcadores de alineación)
    from PIL import Image
    bad_img = Image.new("RGB", (800, 800), color=(240, 240, 240))
    bad_img_bytes = io.BytesIO()
    bad_img.save(bad_img_bytes, format="PNG")
    bad_img_bytes.seek(0)

    # Empaquetar ZIP con:
    # 01_hoja_ok.png (válida)
    # 02_hoja_error.png (imagen blanca sin marcadores OMR)
    # 03_hoja_ok.png (válida)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(hoja_std, arcname="01_hoja_ok.png")
        zf.writestr("02_hoja_error.png", bad_img_bytes.getvalue())
        zf.write(hoja_std, arcname="03_hoja_ok.png")
    zip_buffer.seek(0)

    # Enviar al endpoint principal POST /api/omr/process
    files = {
        "zip_file": ("lote_con_error.zip", zip_buffer.getvalue(), "application/zip"),
        "template": ("template.json", json.dumps(template_obj).encode("utf-8"), "application/json"),
        "evaluation": ("evaluation.json", json.dumps(eval_obj).encode("utf-8"), "application/json"),
    }
    data = {
        "exam_name": "Examen Parcial de Prueba Tarea 3"
    }

    res_proc = client.post("/api/omr/process", files=files, data=data, headers=auth_headers)
    assert res_proc.status_code == 200, f"Error en /api/omr/process: {res_proc.text}"
    batch = res_proc.json()
    job_id = batch["job_id"]
    print(f"  ✓ Lote procesado. Job ID: {job_id}")

    # Verificaciones de manejo de errores
    assert batch["total_files"] == 3, f"Esperado 3 archivos, obtenido {batch['total_files']}"
    assert len(batch["results"]) == 3, "La hoja con error fue eliminada indebidamente"
    assert batch["error_count"] == 1, f"Esperado 1 error, obtenido {batch['error_count']}"
    assert batch["status"] == "completed_with_errors", f"Estado esperado 'completed_with_errors', obtenido '{batch['status']}'"

    # Inspeccionar hoja con error (02_hoja_error.png)
    sheet_results = {r["original_name"]: r for r in batch["results"]}
    err_sheet = sheet_results.get("02_hoja_error.png")
    assert err_sheet is not None, "No se encontró el registro de 02_hoja_error.png"
    assert err_sheet["status"] == "ERROR", f"Estado de hoja errónea debería ser ERROR, es {err_sheet['status']}"
    assert err_sheet["possible_cause"] is not None, "Falta possible_cause en hoja con error"
    assert "marcadores de alineamiento" in err_sheet["possible_cause"], "Explicación de posible causa no coincide con la esperada"
    assert err_sheet["original_image_url"] is not None, "Falta original_image_url en hoja con error"
    print("  ✓ Hoja con error conservada intacta con status='ERROR', explicación visible y URL de imagen original.")

    # ---------------------------------------------------------
    # 4. VISTA DE LA IMAGEN EN CASO DE ERROR
    # ---------------------------------------------------------
    print("\n[4] Comprobando descarga/visualización de imagen de la hoja con error...")
    img_res = client.get(f"/api/omr/jobs/{job_id}/image/{err_sheet['file_id']}", headers=auth_headers)
    assert img_res.status_code == 200, f"No se pudo consultar imagen de error: HTTP {img_res.status_code}"
    assert len(img_res.content) > 0, "Contenido de imagen de error vacío"
    print("  ✓ Imagen original de la hoja fallida servida correctamente con HTTP 200.")

    # ---------------------------------------------------------
    # 5. RECARGA SELECTIVA CON ZIP CORREGIDO (/retry)
    # ---------------------------------------------------------
    print("\n[5] Probando recarga selectiva de ZIP corregido (POST /api/omr/jobs/{job_id}/retry)...")
    # Generamos un ZIP corregido que contiene ÚNICAMENTE la hoja 02_hoja_error.png pero ahora válida
    retry_zip_buffer = io.BytesIO()
    with zipfile.ZipFile(retry_zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(hoja_std, arcname="02_hoja_error.png")
    retry_zip_buffer.seek(0)

    retry_files = {
        "zip_file": ("hoja_02_corregida.zip", retry_zip_buffer.getvalue(), "application/zip")
    }
    res_retry = client.post(f"/api/omr/jobs/{job_id}/retry", files=retry_files, headers=auth_headers)
    assert res_retry.status_code == 200, f"Error en reintento: {res_retry.text}"
    updated_batch = res_retry.json()

    # Comprobaciones tras recarga
    assert updated_batch["total_files"] == 3, f"Se duplicaron registros: total_files={updated_batch['total_files']}"
    assert len(updated_batch["results"]) == 3, f"Resultados duplicados: len={len(updated_batch['results'])}"
    assert updated_batch["error_count"] == 0, f"Aún quedan errores tras corrección: {updated_batch['error_count']}"
    assert updated_batch["status"] == "completed", f"Estado debería ser 'completed', es '{updated_batch['status']}'"

    updated_sheet_results = {r["original_name"]: r for r in updated_batch["results"]}
    corrected_sheet = updated_sheet_results["02_hoja_error.png"]
    assert corrected_sheet["status"] == "SUCCESS", f"La hoja 02 no pasó a SUCCESS: {corrected_sheet['status']}"
    assert corrected_sheet["score"] is not None and corrected_sheet["score"] > 0, "No se calculó puntuación para hoja corregida"
    print("  ✓ Hoja 02 actualizada a SUCCESS sin duplicar hojas 01 y 03.")
    print(f"  ✓ Estado general del examen actualizado a: {updated_batch['status']}.")

    # ---------------------------------------------------------
    # 6. VERIFICACIÓN DE EXPORTACIONES CSV Y EXCEL
    # ---------------------------------------------------------
    print("\n[6] Verificando exportaciones CSV y Excel (columnas dinámicas y paridad)...")
    res_csv = client.get(f"/api/omr/jobs/{job_id}/export/csv", headers=auth_headers)
    assert res_csv.status_code == 200, f"Error al descargar CSV: {res_csv.status_code}"
    csv_text = res_csv.text

    csv_df = pd.read_csv(io.StringIO(csv_text))
    expected_fixed_cols = ["Fecha de carga", "Usuario", "Nombre del examen", "file_id", "score"]
    for col in expected_fixed_cols:
        assert col in csv_df.columns, f"Columna fija '{col}' no encontrada en CSV"

    # Verificar columnas dinámicas q1..q40
    q_cols = [c for c in csv_df.columns if c.startswith("q")]
    assert len(q_cols) == 40, f"Esperadas exactamente 40 columnas de preguntas q1..q40, encontradas {len(q_cols)}"
    assert q_cols[0] == "q1" and q_cols[-1] == "q40", "Rango de columnas no coincide con q1..q40"
    print(f"  ✓ CSV verificado con cabeceras requeridas y exactamente {len(q_cols)} columnas de preguntas dinámicas.")

    # Descargar Excel
    res_xlsx = client.get(f"/api/omr/jobs/{job_id}/export/excel", headers=auth_headers)
    assert res_xlsx.status_code == 200, f"Error al descargar Excel: {res_xlsx.status_code}"
    xlsx_bytes = io.BytesIO(res_xlsx.content)

    excel_file = pd.ExcelFile(xlsx_bytes)
    assert "Resultados" in excel_file.sheet_names, "Falta hoja 'Resultados' en Excel"
    excel_df = pd.read_excel(excel_file, sheet_name="Resultados")

    # Comparar columnas de CSV y Excel Sheet 1
    assert list(csv_df.columns) == list(excel_df.columns), "Discrepancia entre columnas de CSV y Excel"
    assert len(csv_df) == len(excel_df), f"Discrepancia en número de filas: CSV {len(csv_df)} vs Excel {len(excel_df)}"
    print("  ✓ Paridad exacta verificada entre CSV y Hoja 'Resultados' de Excel.")

    print("\n" + "=" * 60)
    print("TODAS LAS PRUEBAS AUTOMATIZADAS DE LA TAREA 3 PASARON EXITOSAMENTE")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
