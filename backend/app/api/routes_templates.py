import json
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.app.schemas.template import (
    TemplateDetail,
    TemplateSummary,
    TemplateValidateResponse,
)
from backend.app.services.template_service import template_service

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=List[TemplateSummary])
async def list_templates():
    return template_service.list_templates()


@router.get("/{template_id:path}", response_model=TemplateDetail)
async def get_template_detail(template_id: str):
    detail = template_service.get_template_detail(template_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Plantilla '{template_id}' no encontrada.")
    return detail


@router.post("", response_model=TemplateDetail)
async def create_template(
    name: str = Form(...),
    config_json: str = Form(..., description="Contenido JSON del template"),
    marker_file: Optional[UploadFile] = File(None, description="Imagen omr_marker.jpg opcional"),
):
    try:
        config_data = json.loads(config_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {str(e)}")

    # Validar contra schema
    val_res = template_service.validate_template_dict(config_data)
    if not val_res.valid:
        raise HTTPException(status_code=422, detail={"message": "Plantilla no cumple el schema", "errors": val_res.errors})

    marker_bytes = None
    if marker_file:
        marker_bytes = await marker_file.read()

    return template_service.save_custom_template(name, config_data, marker_bytes)


@router.post("/validate", response_model=TemplateValidateResponse)
async def validate_template(config_json: str = Form(...)):
    try:
        config_data = json.loads(config_json)
    except Exception as e:
        return TemplateValidateResponse(valid=False, errors=[f"Error de sintaxis JSON: {str(e)}"])

    return template_service.validate_template_dict(config_data)


@router.get("/{template_id:path}/marker")
async def get_template_marker(template_id: str):
    path = template_service.get_template_path(template_id)
    if not path:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada.")

    marker_path = path.parent / "omr_marker.jpg"
    if not marker_path.exists():
        raise HTTPException(status_code=404, detail="Esta plantilla no utiliza marcador de imagen.")

    return FileResponse(path=marker_path, media_type="image/jpeg")

