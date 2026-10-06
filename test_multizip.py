"""
test_multizip.py - Pruebas automatizadas para el soporte de múltiples archivos ZIP
en OMRChecker Web.

Verifica:
1. Validación de extensiones: rechazo de .pdf, .jpg, .txt con HTTP 400 y mensaje claro.
2. Carga y procesamiento de 1 archivo ZIP (compatibilidad).
3. Carga y procesamiento de 2 archivos ZIP simultáneos (zips_summary, sin colisiones).
4. Carga y procesamiento de 5 archivos ZIP (procesamiento controlado).
5. Tolerancia a fallos:
   - ZIP 1: válido -> OK
   - ZIP 2: válido -> OK
   - ZIP 3: corrupto -> ERROR
   - ZIP 4: válido -> OK
   Verifica que el ZIP corrupto no detiene los demás y sus resultados se conservan.
6. Carga secuencial vinculada con job_id (modo append del frontend).
7. Exportación (CSV y Excel) con hojas agregadas de múltiples ZIPs.
8. Historial con conteo de ZIPs (zip_count) y cantidad de hojas.
"""

import io
import json
import zipfile
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

SAMPLE_IMAGE = Path("samples/standard/hoja_estandar.png")
TEMPLATE_JSON = Path("samples/sample1/template.json")


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, data in files.items():
            zf.writestr(fname, data)
    buf.seek(0)
    return buf.getvalue()


def test_validation_rejects_non_zip():
    print("\n--- TEST 1: Validación estricta de extensiones (.zip) ---")
    img_bytes = SAMPLE_IMAGE.read_bytes() if SAMPLE_IMAGE.exists() else b"dummy"

    # Enviar archivo .pdf
    resp = client.post(
        "/api/omr/process",
        files={"zip_files": ("documento.pdf", b"%PDF-1.4 dummy", "application/pdf")},
        data={"exam_name": "Test PDF"},
    )
    assert resp.status_code == 400, f"Se esperaba 400 para PDF, se obtuvo {resp.status_code}"
    assert "Solo se permiten archivos ZIP" in resp.json()["detail"], f"Mensaje incorrecto: {resp.json()}"
    print("✓ Archivo .pdf rechazado correctamente con HTTP 400 y mensaje claro.")

    # Enviar archivo .jpg
    resp2 = client.post(
        "/api/omr/process",
        files={"zip_files": ("examen.jpg", img_bytes, "image/jpeg")},
        data={"exam_name": "Test JPG"},
    )
    assert resp2.status_code == 400
    print("✓ Archivo .jpg rechazado correctamente con HTTP 400.")


def test_single_zip():
    print("\n--- TEST 2: Procesamiento de 1 archivo ZIP ---")
    img_bytes = SAMPLE_IMAGE.read_bytes()
    zip_bytes = make_zip({"sheet1.jpg": img_bytes})

    resp = client.post(
        "/api/omr/process",
        files={"zip_files": ("examen_unico.zip", zip_bytes, "application/zip")},
        data={"exam_name": "Examen 1 ZIP"},
    )
    assert resp.status_code == 200, f"Fallo al procesar 1 ZIP: {resp.text}"
    data = resp.json()
    assert data["total_files"] == 1
    assert data["success_count"] == 1
    assert data["zip_count"] == 1
    assert len(data["zips_summary"]) == 1
    assert data["zips_summary"][0]["filename"] == "examen_unico.zip"
    assert data["zips_summary"][0]["status"] == "COMPLETED"
    print(f"✓ 1 ZIP procesado exitosamente: {data['job_id']} (Total: {data['total_files']}, Score: {data['results'][0]['score']})")
    return data["job_id"]


def test_two_zips():
    print("\n--- TEST 3: Procesamiento de 2 archivos ZIP ---")
    img_bytes = SAMPLE_IMAGE.read_bytes()
    zip1 = make_zip({"sheet1.jpg": img_bytes})
    zip2 = make_zip({"sheet2.jpg": img_bytes})

    resp = client.post(
        "/api/omr/process",
        files=[
            ("zip_files", ("grupo_01.zip", zip1, "application/zip")),
            ("zip_files", ("grupo_02.zip", zip2, "application/zip")),
        ],
        data={"exam_name": "Examen 2 ZIPs"},
    )
    assert resp.status_code == 200, f"Fallo al procesar 2 ZIPs: {resp.text}"
    data = resp.json()
    assert data["total_files"] == 2
    assert data["success_count"] == 2
    assert data["zip_count"] == 2
    assert len(data["zips_summary"]) == 2
    assert data["zips_summary"][0]["filename"] == "grupo_01.zip"
    assert data["zips_summary"][0]["status"] == "COMPLETED"
    assert data["zips_summary"][1]["filename"] == "grupo_02.zip"
    assert data["zips_summary"][1]["status"] == "COMPLETED"
    print(f"✓ 2 ZIPs procesados exitosamente: {data['job_id']} (Total: {data['total_files']} exámenes)")


def test_five_zips_controlled():
    print("\n--- TEST 4: Procesamiento controlado de 5 archivos ZIP ---")
    img_bytes = SAMPLE_IMAGE.read_bytes()
    files_payload = []
    for i in range(1, 6):
        z = make_zip({f"sheet_{i}.jpg": img_bytes})
        files_payload.append(("zip_files", (f"grupo_{i:02d}.zip", z, "application/zip")))

    resp = client.post(
        "/api/omr/process",
        files=files_payload,
        data={"exam_name": "Examen 5 ZIPs"},
    )
    assert resp.status_code == 200, f"Fallo al procesar 5 ZIPs: {resp.text}"
    data = resp.json()
    assert data["total_files"] == 5
    assert data["success_count"] == 5
    assert data["zip_count"] == 5
    assert len(data["zips_summary"]) == 5
    for i, summary in enumerate(data["zips_summary"]):
        assert summary["status"] == "COMPLETED"
    print(f"✓ 5 ZIPs procesados controladamente: {data['job_id']} (Total hojas: {data['total_files']})")


def test_tolerance_corrupt_zip():
    print("\n--- TEST 5: Tolerancia a fallo con ZIP corrupto ---")
    img_bytes = SAMPLE_IMAGE.read_bytes()
    zip1 = make_zip({"sheet_ok1.jpg": img_bytes})
    zip2 = make_zip({"sheet_ok2.jpg": img_bytes})
    zip_corrupt = b"ESTO NO ES UN ARCHIVO ZIP VALIDO CORRUPT BYTES 12345"
    zip3 = make_zip({"sheet_ok3.jpg": img_bytes})

    resp = client.post(
        "/api/omr/process",
        files=[
            ("zip_files", ("valido_01.zip", zip1, "application/zip")),
            ("zip_files", ("valido_02.zip", zip2, "application/zip")),
            ("zip_files", ("corrupto_03.zip", zip_corrupt, "application/zip")),
            ("zip_files", ("valido_04.zip", zip3, "application/zip")),
        ],
        data={"exam_name": "Examen con ZIP corrupto"},
    )
    assert resp.status_code == 200, f"Fallo al responder con ZIP corrupto mezclado: {resp.text}"
    data = resp.json()
    # Las 3 hojas válidas deben procesarse
    assert data["total_files"] == 3
    assert data["success_count"] == 3
    assert data["status"] == "completed_with_errors"

    summaries = {z["filename"]: z for z in data["zips_summary"]}
    assert summaries["valido_01.zip"]["status"] == "COMPLETED"
    assert summaries["valido_02.zip"]["status"] == "COMPLETED"
    assert summaries["corrupto_03.zip"]["status"] == "ERROR"
    assert "corrupt" in summaries["corrupto_03.zip"]["error_message"].lower() or "error" in summaries["corrupto_03.zip"]["error_message"].lower()
    assert summaries["valido_04.zip"]["status"] == "COMPLETED"
    print("✓ El ZIP corrupto fue marcado con ERROR y NO detuvo a los demás ZIPs válidos:")
    for fn, s in summaries.items():
        print(f"   - {fn} → {s['status']}")


def test_sequential_appending_with_job_id():
    print("\n--- TEST 6: Subida secuencial con job_id (modo append del Frontend) ---")
    img_bytes = SAMPLE_IMAGE.read_bytes()
    zip1 = make_zip({"sheet_p1.jpg": img_bytes})
    zip2 = make_zip({"sheet_p2.jpg": img_bytes})

    # 1. Primera subida (crea el job)
    resp1 = client.post(
        "/api/omr/process",
        files={"zip_files": ("secuencia_01.zip", zip1, "application/zip")},
        data={"exam_name": "Examen Secuencial"},
    )
    assert resp1.status_code == 200
    job_id = resp1.json()["job_id"]
    assert resp1.json()["total_files"] == 1

    # 2. Segunda subida (anexa al job existente)
    resp2 = client.post(
        "/api/omr/process",
        files={"zip_files": ("secuencia_02.zip", zip2, "application/zip")},
        data={"job_id": job_id},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["job_id"] == job_id
    assert data2["total_files"] == 2
    assert data2["zip_count"] == 2
    print(f"✓ Anexado exitoso en job {job_id}: ahora contiene {data2['total_files']} exámenes y {data2['zip_count']} ZIPs.")

    # 3. Verificar exportaciones CSV y Excel
    resp_csv = client.get(f"/api/omr/jobs/{job_id}/export/csv")
    assert resp_csv.status_code == 200
    csv_text = resp_csv.text
    assert "sheet_p1.jpg" in csv_text
    assert "sheet_p2.jpg" in csv_text
    print("✓ Exportación CSV contiene todas las hojas de los diferentes ZIPs.")

    resp_excel = client.get(f"/api/omr/jobs/{job_id}/export/excel")
    assert resp_excel.status_code == 200
    print("✓ Exportación Excel generada exitosamente.")

    # 4. Verificar historial
    resp_hist = client.get("/api/omr/history")
    assert resp_hist.status_code == 200
    hist_jobs = resp_hist.json()
    matching = [j for j in hist_jobs if j["job_id"] == job_id]
    assert len(matching) == 1
    assert matching[0]["zip_count"] == 2
    assert matching[0]["total_files"] == 2
    print(f"✓ Historial reporta job {job_id} con zip_count=2 y total_files=2.")


def test_filename_collision_handling():
    print("\n--- TEST 7: Desambiguación de nombres de archivo idénticos en diferentes ZIPs ---")
    img_bytes = SAMPLE_IMAGE.read_bytes()
    # Ambos ZIPs tienen el mismo nombre interno 'sheet1.jpg'
    zip1 = make_zip({"sheet1.jpg": img_bytes})
    zip2 = make_zip({"sheet1.jpg": img_bytes})

    resp = client.post(
        "/api/omr/process",
        files=[
            ("zip_files", ("aula_a.zip", zip1, "application/zip")),
            ("zip_files", ("aula_b.zip", zip2, "application/zip")),
        ],
        data={"exam_name": "Examen Colisión"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files"] == 2
    file_ids = [r["file_id"] for r in data["results"]]
    assert len(set(file_ids)) == 2, f"Los file_ids deben ser únicos para evitar colisiones: {file_ids}"
    print(f"✓ Ambas hojas con nombre idéntico fueron preservadas sin colisiones: {file_ids}")


if __name__ == "__main__":
    print("Iniciando suite de pruebas para soporte MULTI-ZIP...")
    test_validation_rejects_non_zip()
    test_single_zip()
    test_two_zips()
    test_five_zips_controlled()
    test_tolerance_corrupt_zip()
    test_sequential_appending_with_job_id()
    test_filename_collision_handling()
    print("\n==============================================")
    print("✓ TODAS LAS PRUEBAS DE MÚLTIPLES ZIPS PASARON CON ÉXITO")
    print("==============================================")
