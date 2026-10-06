from datetime import datetime, timezone
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.api.routes_auth import get_current_user, get_current_user_optional
from backend.app.core.config import settings
from backend.app.schemas.auth import UserResponse
from backend.app.schemas.omr import (
    BatchProcessResponse,
    JobFilesResponse,
    JobSummaryResponse,
    ProcessedFileInfo,
    SheetResult,
    ZipProcessSummary,
)
from backend.app.services.export_service import export_service
from backend.app.services.omr_engine_service import omr_engine_service
from backend.app.services.storage_service import storage_service

router = APIRouter(prefix="/omr", tags=["OMR Processing"])

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".pdf"}


@router.post("/process", response_model=BatchProcessResponse)
async def process_omr_sheets(
    zip_files: Optional[List[UploadFile]] = File(None, description="Lista de archivos .zip que contienen exámenes OMR"),
    zip_file: Optional[Union[UploadFile, List[UploadFile]]] = File(None, description="Archivo .zip (compatibilidad hacia atrás)"),
    exam_name: Optional[str] = Form("Examen OMR", description="Nombre descriptivo del examen"),
    job_id: Optional[str] = Form(None, description="ID del examen existente para anexar nuevos ZIPs"),
    template: Optional[UploadFile] = File(None, description="Archivo de plantilla (template.json, opcional; estándar por defecto)"),
    evaluation: Optional[UploadFile] = File(None, description="Archivo de evaluación (evaluation.json, opcional)"),
    marker_image: Optional[UploadFile] = File(None, description="Marcador omr_marker.jpg complementario (opcional)"),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    """
    Procesa uno o múltiples archivos ZIP de hojas de examen OMR en una misma operación.
    Soporta streaming en bloques de 1 MB a disco, procesamiento secuencial controlado
    para evitar saturación de memoria, tolerancia a ZIPs corruptos y consolidación de resultados.
    """
    # 0. Recolectar todos los archivos ZIP provistos
    raw_files: List[UploadFile] = []
    if zip_files:
        if isinstance(zip_files, list):
            raw_files.extend(zip_files)
        else:
            raw_files.append(zip_files)
    if zip_file:
        if isinstance(zip_file, list):
            raw_files.extend(zip_file)
        else:
            raw_files.append(zip_file)

    valid_uploads = [f for f in raw_files if f and f.filename]
    if not valid_uploads:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar al menos un archivo .zip.",
        )

    # 1. Validación estricta de extensiones permitidas (.zip)
    for f in valid_uploads:
        ext = Path(f.filename).suffix.lower()
        if ext != ".zip":
            raise HTTPException(
                status_code=400,
                detail=f"Extensión no permitida para '{f.filename}'. Solo se permiten archivos ZIP (.zip).",
            )

    # 2. Validación de nombre del examen
    clean_exam_name = "Examen OMR"
    if exam_name is not None:
        stripped_name = exam_name.strip()
        if stripped_name:
            clean_exam_name = stripped_name
        elif not job_id:
            raise HTTPException(
                status_code=400,
                detail="El nombre del examen es obligatorio.",
            )

    # 3. Espacio de trabajo (nuevo o existente para anexar)
    is_appending = False
    if job_id and job_id.strip():
        target_job_id = job_id.strip()
        paths = storage_service.get_job_paths(target_job_id)
        if paths["root"].exists():
            is_appending = True
            actual_job_id = target_job_id
        else:
            actual_job_id, paths = storage_service.create_job_workspace()
    else:
        actual_job_id, paths = storage_service.create_job_workspace()

    job_info_path = paths["root"] / "job_info.json"
    job_info: Dict[str, Any] = {}
    if is_appending and job_info_path.exists():
        try:
            with job_info_path.open("r", encoding="utf-8") as jf:
                job_info = json.load(jf)
            if clean_exam_name == "Examen OMR" and job_info.get("exam_name"):
                clean_exam_name = job_info["exam_name"]
        except Exception:
            pass

    if not job_info:
        job_info = {
            "job_id": actual_job_id,
            "exam_name": clean_exam_name,
            "user_id": current_user.id if current_user else None,
            "user_email": current_user.correo if current_user else None,
            "user_name": current_user.nombre if current_user else None,
            "status": "processing",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with job_info_path.open("w", encoding="utf-8") as f:
            json.dump(job_info, f, indent=2)

    # 4. Configurar template.json
    template_path = paths["root"] / "template.json"
    t_content: Optional[bytes] = None
    if template and template.filename:
        t_ext = Path(template.filename).suffix.lower()
        if t_ext not in {".json", ".json5"}:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo template debe ser JSON (recibido '{template.filename}').",
            )
        t_content = await template.read()
        if not t_content:
            raise HTTPException(status_code=400, detail="El archivo template.json subido está vacío.")
        try:
            t_data = json.loads(t_content.decode("utf-8"))
            if not isinstance(t_data, dict):
                raise ValueError("El template debe ser un objeto JSON.")
            cols = t_data.get("outputColumns", [])
            if cols:
                from src.utils.parsing import parse_fields
                parsed_cols = parse_fields("Template Columns", cols)
                if len(parsed_cols) > settings.MAX_QUESTIONS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"La plantilla excede el límite máximo de {settings.MAX_QUESTIONS} preguntas (recibido {len(parsed_cols)}).",
                    )
        except HTTPException:
            raise
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Error al analizar template.json: JSON inválido ({str(err)})")
        with template_path.open("wb") as buffer:
            buffer.write(t_content)
    elif not template_path.exists():
        standard_template = settings.STANDARD_TEMPLATE_PATH
        if not standard_template.exists():
            standard_template = settings.SAMPLES_DIR / "sample1" / "template.json"
        if not standard_template.exists():
            raise HTTPException(status_code=500, detail="Plantilla estandarizada no encontrada en el servidor.")
        t_content = standard_template.read_bytes()
        with template_path.open("wb") as buffer:
            buffer.write(t_content)

    # 5. Configurar evaluation (evaluation.json o .csv)
    evaluation_path: Optional[Path] = None
    e_content: Optional[bytes] = None
    for cand in [paths["root"] / "evaluation.json", paths["root"] / "evaluation.csv"]:
        if cand.exists():
            evaluation_path = cand
            break

    if evaluation and evaluation.filename:
        e_ext = Path(evaluation.filename).suffix.lower()
        if e_ext not in {".json", ".csv"}:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo evaluation debe ser .json o .csv (recibido '{evaluation.filename}').",
            )
        e_content = await evaluation.read()
        if not e_content:
            raise HTTPException(status_code=400, detail="El archivo evaluation subido está vacío.")
        if e_ext == ".json":
            try:
                e_data = json.loads(e_content.decode("utf-8"))
                if not isinstance(e_data, dict):
                    raise ValueError("El evaluation debe ser un objeto JSON.")
                opts = e_data.get("options", {})
                q_list = opts.get("questions_in_order", [])
                if isinstance(q_list, list) and len(q_list) > 0:
                    from src.utils.parsing import parse_fields
                    parsed_qs = parse_fields("Questions", q_list)
                    if len(parsed_qs) > settings.MAX_QUESTIONS:
                        raise HTTPException(
                            status_code=400,
                            detail=f"El examen no puede exceder el límite máximo de {settings.MAX_QUESTIONS} preguntas (recibido {len(parsed_qs)}).",
                        )
                    if len(parsed_qs) == 0:
                        raise HTTPException(
                            status_code=400,
                            detail="El archivo de evaluación debe contener al menos 1 pregunta.",
                        )
            except HTTPException:
                raise
            except Exception as err:
                raise HTTPException(status_code=400, detail=f"Error al analizar evaluation.json: JSON inválido ({str(err)})")
        evaluation_path = paths["root"] / f"evaluation{e_ext}"
        with evaluation_path.open("wb") as buffer:
            buffer.write(e_content)

    # 6. Configurar marcador de calibración y config.json
    target_marker = paths["root"] / "omr_marker.jpg"
    if marker_image and marker_image.filename:
        m_content = await marker_image.read()
        with target_marker.open("wb") as buffer:
            buffer.write(m_content)
    elif not target_marker.exists():
        default_marker = settings.STANDARD_TEMPLATE_DIR / "omr_marker.jpg"
        if not default_marker.exists():
            default_marker = settings.SAMPLES_DIR / "sample1" / "omr_marker.jpg"
        if default_marker.exists():
            import shutil
            shutil.copy(default_marker, target_marker)

    job_config_path = paths["root"] / "config.json"
    if not job_config_path.exists():
        default_config = settings.STANDARD_TEMPLATE_DIR / "config.json"
        if default_config.exists():
            import shutil
            shutil.copy(default_config, job_config_path)

    # 7. Cargar resultados previos si estamos anexando
    existing_results: List[SheetResult] = []
    existing_zips_summary: List[ZipProcessSummary] = []
    results_json_file = paths["results"] / "results.json"
    if is_appending and results_json_file.exists():
        try:
            with results_json_file.open("r", encoding="utf-8") as rf:
                old_data = json.load(rf)
                existing_results = [SheetResult(**r) for r in old_data.get("results", [])]
                existing_zips_summary = [ZipProcessSummary(**z) for z in old_data.get("zips_summary", [])]
        except Exception:
            pass

    seen_file_ids = {r.file_id for r in existing_results}
    all_results: List[SheetResult] = list(existing_results)
    zips_summary: List[ZipProcessSummary] = list(existing_zips_summary)

    # 8. Procesamiento controlado secuencial de cada ZIP
    import gc
    import shutil

    temp_uploads_dir = paths["root"] / "temp_uploads"
    temp_uploads_dir.mkdir(parents=True, exist_ok=True)
    chunk_size = settings.UPLOAD_CHUNK_SIZE_BYTES

    for idx, z_upload in enumerate(valid_uploads):
        zip_filename = Path(z_upload.filename).name or f"archivo_{idx}.zip"
        zip_stem = Path(zip_filename).stem
        temp_zip_path = temp_uploads_dir / f"up_{idx}_{zip_filename}"

        total_bytes = 0
        stream_error = None
        try:
            with temp_zip_path.open("wb") as buffer:
                while True:
                    chunk = await z_upload.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > settings.MAX_ZIP_SIZE_BYTES:
                        max_mb = settings.MAX_ZIP_SIZE_BYTES // (1024 * 1024)
                        raise ValueError(f"El archivo ZIP excede el tamaño máximo permitido ({max_mb} MB).")
                    buffer.write(chunk)
        except Exception as read_err:
            stream_error = str(read_err)
        finally:
            try:
                await z_upload.close()
            except Exception:
                pass

        if stream_error:
            if temp_zip_path.exists():
                try:
                    temp_zip_path.unlink()
                except Exception:
                    pass
            zips_summary.append(ZipProcessSummary(
                filename=zip_filename,
                status="ERROR",
                error_message=f"Error durante la lectura en streaming: {stream_error}",
            ))
            continue

        if total_bytes == 0:
            if temp_zip_path.exists():
                try:
                    temp_zip_path.unlink()
                except Exception:
                    pass
            zips_summary.append(ZipProcessSummary(
                filename=zip_filename,
                status="ERROR",
                error_message="El archivo ZIP está vacío (0 bytes).",
            ))
            continue

        # Extracción segura en subcarpeta aislada dentro de inputs/
        zip_extract_dir = paths["inputs"] / f"z_{len(zips_summary)}_{zip_stem}"
        zip_extract_dir.mkdir(parents=True, exist_ok=True)
        extract_error = None
        try:
            storage_service.extract_zip_safely(
                temp_zip_path,
                zip_extract_dir,
                max_uncompressed_bytes=settings.MAX_UNCOMPRESSED_BYTES,
            )
        except Exception as ext_err:
            extract_error = str(ext_err)
        finally:
            # Eliminar archivo ZIP temporal para liberar disco
            if temp_zip_path.exists():
                try:
                    temp_zip_path.unlink()
                except Exception:
                    pass

        if extract_error:
            shutil.rmtree(zip_extract_dir, ignore_errors=True)
            zips_summary.append(ZipProcessSummary(
                filename=zip_filename,
                status="ERROR",
                error_message=f"Error al extraer ZIP: {extract_error}",
            ))
            continue

        # Detectar imágenes válidas en el ZIP
        valid_images, extracted_marker = storage_service.get_valid_input_images(zip_extract_dir)
        if not valid_images:
            shutil.rmtree(zip_extract_dir, ignore_errors=True)
            zips_summary.append(ZipProcessSummary(
                filename=zip_filename,
                status="ERROR",
                error_message="El archivo ZIP no contiene ninguna imagen u hoja OMR válida.",
            ))
            continue

        if not target_marker.exists() and extracted_marker and extracted_marker.exists():
            shutil.copy(extracted_marker, target_marker)

        # Evitar colisión de nombres entre diferentes ZIPs
        prepared_images: List[Path] = []
        for img_path in valid_images:
            target_img_path = img_path
            if img_path.name in seen_file_ids:
                new_file_name = f"{zip_stem}_{img_path.name}"
                new_path = img_path.parent / new_file_name
                try:
                    img_path.rename(new_path)
                    target_img_path = new_path
                except Exception:
                    pass
            seen_file_ids.add(target_img_path.name)
            prepared_images.append(target_img_path)

        # Ejecutar procesamiento OMR para las hojas de este ZIP
        try:
            sub_batch = omr_engine_service.process_batch(
                file_paths=prepared_images,
                template_path=template_path,
                evaluation_path=evaluation_path,
                config_path=job_config_path if job_config_path.exists() else None,
                job_id=actual_job_id,
                output_dir=paths["outputs"],
            )

            for r in sub_batch.results:
                all_results.append(r)

            zips_summary.append(ZipProcessSummary(
                filename=zip_filename,
                status="COMPLETED",
                total_sheets=len(prepared_images),
                success_count=sum(1 for s in sub_batch.results if s.status != "ERROR"),
                error_count=sum(1 for s in sub_batch.results if s.status == "ERROR"),
            ))
        except Exception as batch_err:
            zips_summary.append(ZipProcessSummary(
                filename=zip_filename,
                status="ERROR",
                total_sheets=len(prepared_images),
                error_count=len(prepared_images),
                error_message=f"Error durante el procesamiento OMR: {str(batch_err)}",
            ))

        # Liberar memoria de imágenes procesadas y garbage collector
        gc.collect()

    if temp_uploads_dir.exists():
        shutil.rmtree(temp_uploads_dir, ignore_errors=True)

    # 9. Si ningún archivo ZIP pudo ser procesado en una carga inicial, lanzar error claro
    if not is_appending and not all_results and all(z.status == "ERROR" for z in zips_summary):
        storage_service.remove_job_workspace(actual_job_id)
        err_msg = zips_summary[0].error_message if zips_summary else "No fue posible procesar ningún archivo ZIP."
        raise HTTPException(status_code=400, detail=err_msg)

    # 10. Consolidar estadísticas y métricas del examen
    total_files = len(all_results)
    success_count = sum(1 for r in all_results if r.status == "SUCCESS")
    multi_marked_count = sum(1 for r in all_results if r.status == "MULTI_MARKED" or r.multi_marked)
    incompletas_count = sum(1 for r in all_results if r.status == "INCOMPLETA" or r.incompletas > 0)
    error_count = sum(1 for r in all_results if r.status == "ERROR")

    valid_scores = [r.score for r in all_results if r.status != "ERROR"]
    avg_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0
    highest = round(max(valid_scores), 2) if valid_scores else 0.0
    lowest = round(min(valid_scores), 2) if valid_scores else 0.0

    parsed_q_count = None
    if evaluation_path and evaluation_path.exists():
        try:
            with evaluation_path.open("r", encoding="utf-8") as ev_f:
                e_tmp = json.load(ev_f)
                qs = e_tmp.get("options", {}).get("questions_in_order", [])
                if qs:
                    from src.utils.parsing import parse_fields
                    parsed_q_count = len(parse_fields("Questions", qs))
        except Exception:
            pass

    if parsed_q_count is None and all_results and all_results[0].audits:
        parsed_q_count = len(all_results[0].audits)

    overall_status = "completed"
    if error_count > 0 or any(z.status == "ERROR" for z in zips_summary):
        overall_status = "completed_with_errors"

    batch_response = BatchProcessResponse(
        job_id=actual_job_id,
        exam_name=clean_exam_name,
        status=overall_status,
        total_files=total_files,
        success_count=success_count,
        multi_marked_count=multi_marked_count,
        incompletas_count=incompletas_count,
        error_count=error_count,
        average_score=avg_score,
        highest_score=highest,
        lowest_score=lowest,
        question_count=parsed_q_count,
        scoring_mode="EQUAL" if parsed_q_count else None,
        zip_count=len(zips_summary),
        zips_summary=zips_summary,
        results=all_results,
        created_at=job_info.get("created_at"),
        user_id=current_user.id if current_user else job_info.get("user_id"),
        user_email=current_user.correo if current_user else job_info.get("user_email"),
        user_name=current_user.nombre if current_user else job_info.get("user_name"),
    )

    # 11. Actualizar job_info.json
    job_info["status"] = batch_response.status
    job_info["question_count"] = batch_response.question_count
    job_info["created_at"] = batch_response.created_at
    job_info["zip_count"] = batch_response.zip_count
    job_info["zips_summary"] = [z.model_dump() for z in zips_summary]
    with job_info_path.open("w", encoding="utf-8") as f:
        json.dump(job_info, f, indent=2)

    # 12. Guardar reportes consolidados (results.json, results.csv, results.xlsx)
    export_service.save_batch_results(batch_response, paths["results"])

    return batch_response


@router.get("/jobs/{job_id}", response_model=JobSummaryResponse, tags=["OMR Jobs"])
async def get_job_summary(job_id: str):
    """
    Devuelve el estado general del trabajo OMR identificado por job_id.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    json_path = paths["results"] / "results.json"
    job_info_path = paths["root"] / "job_info.json"
    input_files_count = len([f for f in paths["inputs"].rglob("*") if f.is_file()]) if paths["inputs"].exists() else 0
    processed_images_count = len(list(paths["outputs"].glob("*"))) if paths["outputs"].exists() else 0

    exam_name_fallback = "Examen OMR"
    if job_info_path.exists():
        try:
            with job_info_path.open("r", encoding="utf-8") as f:
                info_data = json.load(f)
                exam_name_fallback = info_data.get("exam_name", "Examen OMR")
        except Exception:
            pass

    if not json_path.exists():
        return JobSummaryResponse(
            job_id=job_id,
            exam_name=exam_name_fallback,
            status="pending",
            has_results=False,
            has_outputs=processed_images_count > 0,
            input_files_count=input_files_count,
            processed_images_count=processed_images_count,
            total_files=input_files_count,
        )

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al leer results.json para el trabajo '{job_id}': {str(e)}",
        )

    q_cnt = data.get("question_count")
    if not q_cnt and "results" in data and len(data["results"]) > 0:
        audits = data["results"][0].get("audits", [])
        q_cnt = len(audits) if audits else None

    return JobSummaryResponse(
        job_id=job_id,
        exam_name=data.get("exam_name", exam_name_fallback),
        question_count=q_cnt,
        status=data.get("status", "completed"),
        created_at=data.get("created_at"),
        user_id=data.get("user_id"),
        user_email=data.get("user_email"),
        user_name=data.get("user_name"),
        total_files=data.get("total_files", input_files_count),
        success_count=data.get("success_count", 0),
        multi_marked_count=data.get("multi_marked_count", 0),
        error_count=data.get("error_count", 0),
        average_score=data.get("average_score", 0.0),
        highest_score=data.get("highest_score", 0.0),
        lowest_score=data.get("lowest_score", 0.0),
        zip_count=data.get("zip_count", len(data.get("zips_summary", [])) or 1),
        zips_summary=data.get("zips_summary"),
        has_results=True,
        has_outputs=processed_images_count > 0,
        input_files_count=input_files_count,
        processed_images_count=processed_images_count,
    )


@router.get("/jobs/{job_id}/results", response_model=BatchProcessResponse, tags=["OMR Jobs"])
async def get_job_results(job_id: str):
    """
    Devuelve los resultados estructurados completos contenidos en results.json.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    json_path = paths["results"] / "results.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Archivo results.json no encontrado para el trabajo '{job_id}'.",
        )

    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al leer el archivo results.json: {str(e)}",
        )

    return data


@router.get("/jobs/{job_id}/files", response_model=JobFilesResponse, tags=["OMR Jobs"])
async def get_job_processed_files(job_id: str):
    """
    Devuelve las rutas, nombres y URLs de descarga/visualización de las imágenes procesadas.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    if not paths["outputs"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Directorio de imágenes procesadas (outputs) no encontrado para el trabajo '{job_id}'.",
        )

    processed_files: List[ProcessedFileInfo] = []
    for file_path in sorted(paths["outputs"].iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
            processed_files.append(
                ProcessedFileInfo(
                    filename=file_path.name,
                    url=f"/api/omr/jobs/{job_id}/image/{file_path.name}",
                    path=str(file_path),
                    size_bytes=file_path.stat().st_size,
                )
            )

    return JobFilesResponse(
        job_id=job_id,
        total_files=len(processed_files),
        files=processed_files,
    )


@router.get("/jobs/{job_id}/image/{filename}", tags=["OMR Jobs"])
async def get_job_marked_image(job_id: str, filename: str):
    """
    Visualiza la imagen procesada con detecciones OMR (outputs/marked_...).
    Si la hoja falló y no existe imagen procesada, entrega la imagen original de entrada como fallback.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    # 1. Si filename empieza por marked_, buscar en outputs
    if filename.startswith("marked_"):
        target_path = paths["outputs"] / filename
        if not target_path.exists() or not target_path.is_file():
            target_path = paths["outputs"] / filename[len("marked_"):]
        if not target_path.exists() or not target_path.is_file():
            clean_in = filename[len("marked_"):]
            target_path = paths["inputs"] / clean_in
            if not target_path.exists() or not target_path.is_file():
                for f in paths["inputs"].rglob(clean_in):
                    if f.is_file():
                        target_path = f
                        break
    else:
        # Si filename no tiene prefijo, priorizar la imagen procesada marked_ en outputs
        target_path = paths["outputs"] / f"marked_{filename}"
        if not target_path.exists() or not target_path.is_file():
            target_path = paths["outputs"] / filename
        if not target_path.exists() or not target_path.is_file():
            target_path = paths["inputs"] / filename
            if not target_path.exists() or not target_path.is_file():
                for f in paths["inputs"].rglob(filename):
                    if f.is_file():
                        target_path = f
                        break

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Imagen '{filename}' no encontrada en el trabajo '{job_id}'.",
        )

    mime_type, _ = mimetypes.guess_type(str(target_path))
    return FileResponse(path=target_path, media_type=mime_type or "image/jpeg")


@router.get("/jobs/{job_id}/original-image/{filename}", tags=["OMR Jobs"])
async def get_job_original_image(job_id: str, filename: str):
    """
    Descarga o visualiza la imagen original cargada (inputs/), útil para inspeccionar hojas con ERROR.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    clean_name = filename[len("marked_"):] if filename.startswith("marked_") else filename
    target_path = paths["inputs"] / clean_name

    if not target_path.exists() or not target_path.is_file():
        for f in paths["inputs"].rglob(clean_name):
            if f.is_file():
                target_path = f
                break

    if not target_path.exists() or not target_path.is_file():
        # Fallback a outputs si no estuviera en inputs
        target_path = paths["outputs"] / clean_name

    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Imagen original '{filename}' no encontrada en el trabajo '{job_id}'.",
        )

    mime_type, _ = mimetypes.guess_type(str(target_path))
    return FileResponse(path=target_path, media_type=mime_type or "image/jpeg")


@router.get("/jobs/{job_id}/export/csv", tags=["OMR Export"])
async def export_job_csv(job_id: str):
    """
    Exporta los resultados del trabajo en formato CSV compatible con OMRChecker.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    csv_path = paths["results"] / "results.csv"
    if not csv_path.exists():
        json_path = paths["results"] / "results.json"
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                batch = BatchProcessResponse.model_validate_json(f.read())
            export_service.save_batch_results(batch, paths["results"])
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Resultados no disponibles para el trabajo '{job_id}'.",
            )

    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=f"omr_resultados_{job_id[:8]}.csv",
    )


@router.get("/jobs/{job_id}/export/excel", tags=["OMR Export"])
async def export_job_excel(job_id: str):
    """
    Exporta los resultados del trabajo en formato Excel (.xlsx con openpyxl) con hojas 'Resultados' y 'Detalle'.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    xlsx_path = paths["results"] / "results.xlsx"
    if not xlsx_path.exists():
        json_path = paths["results"] / "results.json"
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                batch = BatchProcessResponse.model_validate_json(f.read())
            export_service.save_batch_results(batch, paths["results"])
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Resultados no disponibles para el trabajo '{job_id}'.",
            )

    return FileResponse(
        path=xlsx_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"omr_resultados_{job_id[:8]}.xlsx",
    )


@router.post("/jobs/{job_id}/retry", response_model=BatchProcessResponse, tags=["OMR Processing"])
async def retry_job_with_corrected_zip(
    job_id: str,
    zip_file: UploadFile = File(..., description="Archivo .zip que contiene hojas OMR corregidas"),
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    """
    Vuelve a procesar un conjunto de hojas corregidas sobre un examen existente.
    Conserva la configuración original (template, evaluación, puntos, nombre de examen).
    Actualiza los registros existentes sin duplicar los correctos.
    """
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo '{job_id}' no encontrado en storage/jobs/.",
        )

    json_path = paths["results"] / "results.json"
    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Resultados no disponibles para el trabajo '{job_id}'.",
        )

    # 1. Leer resultados actuales
    try:
        with json_path.open("r", encoding="utf-8") as f:
            batch_data = json.load(f)
        current_batch = BatchProcessResponse.model_validate(batch_data)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al leer resultados actuales del examen: {str(e)}",
        )

    # 2. Validar que el archivo subido sea un ZIP válido
    if not zip_file or not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar un archivo con extensión .zip.",
        )

    # 3. Guardar y extraer el ZIP corregido en inputs por chunks de 1 MB
    retry_zip_path = paths["root"] / f"retry_{Path(zip_file.filename).name}"
    total_bytes = 0
    chunk_size = settings.UPLOAD_CHUNK_SIZE_BYTES
    try:
        with retry_zip_path.open("wb") as buffer:
            while True:
                chunk = await zip_file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_ZIP_SIZE_BYTES:
                    buffer.close()
                    max_mb = settings.MAX_ZIP_SIZE_BYTES // (1024 * 1024)
                    raise HTTPException(
                        status_code=400,
                        detail=f"El archivo ZIP corregido excede el tamaño máximo permitido ({max_mb} MB).",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as read_err:
        raise HTTPException(
            status_code=400,
            detail=f"Error durante la lectura en streaming del archivo ZIP corregido: {str(read_err)}",
        )
    finally:
        try:
            await zip_file.close()
        except Exception:
            pass

    try:
        storage_service.extract_zip_safely(
            retry_zip_path,
            paths["inputs"],
            max_uncompressed_bytes=settings.MAX_UNCOMPRESSED_BYTES,
        )
    except Exception as err:
        raise HTTPException(
            status_code=400,
            detail=f"Error al extraer archivo ZIP corregido: {str(err)}",
        )

    # 4. Identificar qué imágenes llegaron en el nuevo ZIP
    import zipfile
    corrected_filenames = set()
    with zipfile.ZipFile(retry_zip_path, "r") as zf:
        for name in zf.namelist():
            p = Path(name)
            if p.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                corrected_filenames.add(p.name)

    if not corrected_filenames:
        raise HTTPException(
            status_code=400,
            detail="El ZIP corregido no contiene hojas OMR compatibles (.jpg, .jpeg, .png).",
        )

    # Rutas absolutas de las imágenes corregidas
    target_files = [paths["inputs"] / fn for fn in corrected_filenames if (paths["inputs"] / fn).exists()]

    # 5. Obtener configuración original del examen
    template_path = paths["root"] / "template.json"
    evaluation_path = paths["root"] / "evaluation.json"
    if not evaluation_path.exists():
        evaluation_path = None
    config_path = paths["root"] / "config.json"
    if not config_path.exists():
        config_path = None

    # 6. Procesar las hojas corregidas con la configuración original
    try:
        new_batch = omr_engine_service.process_batch(
            file_paths=target_files,
            template_path=template_path,
            evaluation_path=evaluation_path,
            config_path=config_path,
            job_id=job_id,
            output_dir=paths["outputs"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar las hojas corregidas: {str(e)}",
        )

    # 7. Actualizar sin duplicar:
    # Mapear los nuevos resultados por original_name
    new_results_map = {r.original_name: r for r in new_batch.results}
    merged_results = []
    updated_names = set()

    for old_r in current_batch.results:
        if old_r.original_name in new_results_map:
            # Reemplazar el registro con el nuevo resultado (sea exitoso o con nuevo error)
            merged_results.append(new_results_map[old_r.original_name])
            updated_names.add(old_r.original_name)
        else:
            merged_results.append(old_r)

    # Agregar archivos adicionales si no estaban en el lote original
    for name, r in new_results_map.items():
        if name not in updated_names:
            merged_results.append(r)

    # 8. Recalcular métricas
    current_batch.results = merged_results
    current_batch.total_files = len(merged_results)
    current_batch.success_count = sum(1 for r in merged_results if r.status == "SUCCESS")
    current_batch.multi_marked_count = sum(1 for r in merged_results if r.status == "MULTI_MARKED")
    current_batch.error_count = sum(1 for r in merged_results if r.status == "ERROR")

    valid_scores = [r.score for r in merged_results if r.status != "ERROR"]
    current_batch.average_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0
    current_batch.highest_score = max(valid_scores) if valid_scores else 0.0
    current_batch.lowest_score = min(valid_scores) if valid_scores else 0.0
    current_batch.status = "completed_with_errors" if current_batch.error_count > 0 else "completed"

    # 9. Guardar reportes actualizados (results.json, results.csv, results.xlsx)
    export_service.save_batch_results(current_batch, paths["results"])

    # 10. Actualizar job_info.json
    job_info_path = paths["root"] / "job_info.json"
    if job_info_path.exists():
        try:
            with job_info_path.open("r", encoding="utf-8") as f:
                j_info = json.load(f)
            j_info["status"] = current_batch.status
            j_info["error_count"] = current_batch.error_count
            with job_info_path.open("w", encoding="utf-8") as f:
                json.dump(j_info, f, indent=2)
        except Exception:
            pass

    return current_batch


@router.get("/history", response_model=List[JobSummaryResponse], tags=["OMR Jobs"])
@router.get("/exams", response_model=List[JobSummaryResponse], tags=["OMR Jobs"])
@router.get("/jobs", response_model=List[JobSummaryResponse], tags=["OMR Jobs"])
async def get_user_exam_history(
    current_user: Optional[UserResponse] = Depends(get_current_user_optional),
):
    """
    Devuelve la lista de exámenes procesados correspondientes al usuario autenticado.
    Si el examen no tiene usuario asignado (procesado anteriormente), también se incluye.
    """
    user_jobs: List[JobSummaryResponse] = []
    jobs_dir = settings.JOBS_DIR
    if not jobs_dir.exists():
        return user_jobs

    for job_dir in sorted(jobs_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
        if not job_dir.is_dir():
            continue

        job_id = job_dir.name
        results_file = job_dir / "results" / "results.json"
        job_info_file = job_dir / "job_info.json"

        if results_file.exists():
            try:
                with results_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                job_user_id = data.get("user_id")
                # Si hay usuario autenticado: ocultar solo si pertenece a OTRO usuario diferente
                if current_user and job_user_id and job_user_id != current_user.id:
                    continue

                q_cnt = data.get("question_count")
                if not q_cnt and "results" in data and len(data["results"]) > 0:
                    audits = data["results"][0].get("audits", [])
                    q_cnt = len(audits) if audits else None

                err_cnt = data.get("error_count", 0)
                status_val = data.get("status", "completed")
                if err_cnt > 0 and status_val == "completed":
                    status_val = "completed_with_errors"

                user_jobs.append(
                    JobSummaryResponse(
                        job_id=job_id,
                        exam_name=data.get("exam_name", "Examen OMR"),
                        question_count=q_cnt,
                        status=status_val,
                        created_at=data.get("created_at"),
                        user_id=data.get("user_id"),
                        user_email=data.get("user_email"),
                        user_name=data.get("user_name"),
                        total_files=data.get("total_files", 0),
                        success_count=data.get("success_count", 0),
                        multi_marked_count=data.get("multi_marked_count", 0),
                        error_count=err_cnt,
                        average_score=data.get("average_score", 0.0),
                        highest_score=data.get("highest_score", 0.0),
                        lowest_score=data.get("lowest_score", 0.0),
                        zip_count=data.get("zip_count", len(data.get("zips_summary", [])) or 1),
                        zips_summary=data.get("zips_summary"),
                        has_results=True,
                        has_outputs=True,
                        input_files_count=data.get("total_files", 0),
                        processed_images_count=data.get("total_files", 0),
                    )
                )
            except Exception:
                continue
        elif job_info_file.exists():
            try:
                with job_info_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                job_user_id = data.get("user_id")
                if current_user and job_user_id and job_user_id != current_user.id:
                    continue

                user_jobs.append(
                    JobSummaryResponse(
                        job_id=job_id,
                        exam_name=data.get("exam_name", "Examen OMR"),
                        question_count=data.get("question_count"),
                        status=data.get("status", "processing"),
                        created_at=data.get("created_at"),
                        user_id=data.get("user_id"),
                        user_email=data.get("user_email"),
                        user_name=data.get("user_name"),
                        total_files=0,
                        has_results=False,
                        has_outputs=False,
                    )
                )
            except Exception:
                continue

    return user_jobs

