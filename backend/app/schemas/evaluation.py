from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationSummary(BaseModel):
    id: str
    name: str
    source_type: str  # "custom" o "csv"
    total_questions: int = 0
    sections: List[str] = Field(default_factory=list)


class EvaluationDetail(BaseModel):
    id: str
    name: str
    config: Dict[str, Any]


class EvaluationCreateRequest(BaseModel):
    name: str
    config: Dict[str, Any]


class EvaluationValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)

