"""
exam.py - Esquemas Pydantic para creación, edición y consulta de Exámenes OMR.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ExamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Nombre o título del examen")
    description: Optional[str] = Field(None, max_length=1000, description="Descripción opcional")
    question_count: int = Field(40, ge=1, le=40, description="Cantidad de preguntas (1 a 40)")
    scoring_mode: str = Field("EQUAL", description="Modalidad de puntuación: EQUAL o SPECIFIC")
    equal_points: float = Field(1.0, gt=0, description="Puntaje por pregunta en modalidad EQUAL")
    specific_points: Optional[Dict[str, float]] = Field(None, description="Puntajes específicos por pregunta")
    answers: Dict[str, str] = Field(..., description="Pauta de respuestas correctas { '1': 'A', '2': 'B', ... }")
    enabled_for_all: bool = Field(True, description="Si está habilitado para todos los estudiantes/usuarios")
    enabled_user_ids: Optional[List[str]] = Field(default_factory=list, description="Lista de IDs de usuarios habilitados si no es para todos")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("El nombre del examen no puede estar vacío.")
        return clean

    @field_validator("scoring_mode")
    @classmethod
    def validate_scoring_mode(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in ("EQUAL", "SPECIFIC"):
            raise ValueError("Modalidad de puntuación no válida. Debe ser EQUAL o SPECIFIC.")
        return clean

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, v: Dict[str, str], info) -> Dict[str, str]:
        q_count = info.data.get("question_count", 40)
        clean_answers: Dict[str, str] = {}
        valid_options = {"A", "B", "C", "D", "E"}
        for i in range(1, q_count + 1):
            val = v.get(str(i)) or v.get(f"q{i}") or v.get(i)
            if not val or str(val).strip().upper() not in valid_options:
                raise ValueError(f"Falta asignar una respuesta válida (A, B, C, D o E) para la pregunta {i}.")
            clean_answers[str(i)] = str(val).strip().upper()
        return clean_answers


class ExamUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    question_count: Optional[int] = Field(None, ge=1, le=40)
    scoring_mode: Optional[str] = None
    equal_points: Optional[float] = Field(None, gt=0)
    specific_points: Optional[Dict[str, float]] = None
    answers: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None
    enabled_for_all: Optional[bool] = None
    enabled_user_ids: Optional[List[str]] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        clean = v.strip()
        if not clean:
            raise ValueError("El nombre del examen no puede estar vacío.")
        return clean

    @field_validator("scoring_mode")
    @classmethod
    def validate_scoring_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        clean = v.strip().upper()
        if clean not in ("EQUAL", "SPECIFIC"):
            raise ValueError("Modalidad de puntuación no válida. Debe ser EQUAL o SPECIFIC.")
        return clean


class ExamResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    creator_id: str
    creator_name: str
    creator_email: str
    question_count: int
    scoring_mode: str
    equal_points: float
    specific_points: Optional[Dict[str, float]] = None
    answers: Optional[Dict[str, str]] = None  # Se omite para el rol 'usuario' para proteger la pauta
    is_active: bool = True
    enabled_for_all: bool = True
    enabled_user_ids: List[str] = Field(default_factory=list)
    assigned_count: Optional[int] = 0
    created_at: str
    updated_at: str


class ExamAssignmentRequest(BaseModel):
    user_ids: List[str] = Field(..., min_length=1, description="Lista de IDs de usuarios a asignar")


class AssignedUserDetail(BaseModel):
    id: str
    nombre: str
    correo: str
    assigned_at: str
    assigned_by: str
    assigned_by_name: Optional[str] = None
    status: str = "active"


class ExamAssignmentResponse(BaseModel):
    exam_id: str
    exam_name: str
    assigned_count: int
    total_assigned: int
    assigned_users: List[AssignedUserDetail] = []
    message: str = "Asignación exitosa"


