import json
from typing import List

from fastapi import APIRouter, Body, HTTPException

from backend.app.schemas.evaluation import (
    EvaluationCreateRequest,
    EvaluationDetail,
    EvaluationSummary,
    EvaluationValidateResponse,
)
from backend.app.services.evaluation_service import evaluation_service

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


@router.get("", response_model=List[EvaluationSummary])
async def list_evaluations():
    return evaluation_service.list_evaluations()


@router.get("/{eval_id:path}", response_model=EvaluationDetail)
async def get_evaluation_detail(eval_id: str):
    detail = evaluation_service.get_evaluation_detail(eval_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Pauta '{eval_id}' no encontrada.")
    return detail


@router.post("", response_model=EvaluationDetail)
async def create_evaluation(payload: EvaluationCreateRequest):
    val_res = evaluation_service.validate_evaluation_dict(payload.config)
    if not val_res.valid:
        raise HTTPException(
            status_code=422,
            detail={"message": "Pauta de evaluación no cumple el schema", "errors": val_res.errors},
        )

    return evaluation_service.save_custom_evaluation(payload.name, payload.config)


@router.post("/validate", response_model=EvaluationValidateResponse)
async def validate_evaluation(payload: dict = Body(...)):
    return evaluation_service.validate_evaluation_dict(payload)

