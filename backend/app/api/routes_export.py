from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.responses import FileResponse

from backend.app.schemas.omr import BatchProcessResponse
from backend.app.services.export_service import export_service
from backend.app.services.storage_service import storage_service

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/{job_id}/csv")
async def export_job_csv(job_id: str):
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(status_code=404, detail=f"Trabajo '{job_id}' no encontrado.")

    csv_path = paths["results"] / "results.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Archivo CSV no encontrado para este trabajo.")
        json_path = paths["results"] / "results.json"
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                batch = BatchProcessResponse.model_validate_json(f.read())
            export_service.save_batch_results(batch, paths["results"])
        else:
            raise HTTPException(status_code=404, detail="Archivo CSV no encontrado para este trabajo.")

    return FileResponse(
        path=csv_path,
        media_type="text/csv",
        filename=f"omr_resultados_{job_id[:8]}.csv",
    )


@router.get("/{job_id}/excel")
async def export_job_excel(job_id: str):
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(status_code=404, detail=f"Trabajo '{job_id}' no encontrado.")

    xlsx_path = paths["results"] / "results.xlsx"
    if not xlsx_path.exists():
        raise HTTPException(status_code=404, detail="Archivo Excel no encontrado para este trabajo.")
        json_path = paths["results"] / "results.json"
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                batch = BatchProcessResponse.model_validate_json(f.read())
            export_service.save_batch_results(batch, paths["results"])
        else:
            raise HTTPException(status_code=404, detail="Archivo Excel no encontrado para este trabajo.")

    return FileResponse(
        path=xlsx_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"omr_resultados_{job_id[:8]}.xlsx",
    )


@router.get("/{job_id}/json")
async def export_job_json(job_id: str):
    paths = storage_service.get_job_paths(job_id)
    if not paths["root"].exists():
        raise HTTPException(status_code=404, detail=f"Trabajo '{job_id}' no encontrado.")

    json_path = paths["results"] / "results.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Archivo JSON no encontrado para este trabajo.")

    return FileResponse(
        path=json_path,
        media_type="application/json",
        filename=f"omr_resultados_{job_id[:8]}.json",
    )

