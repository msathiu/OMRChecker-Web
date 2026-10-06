from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QuestionAudit(BaseModel):
    question: str
    marked: str
    allowed_answers: Any = None
    verdict: str
    delta: float
    score: float
    section: Optional[str] = None


class SheetResult(BaseModel):
    file_id: str
    original_name: str
    page_number: Optional[int] = 1
    score: float = 0.0
    max_score: Optional[float] = None
    percentage: Optional[float] = None
    status: str = "SUCCESS"  # SUCCESS, MULTI_MARKED, ERROR
    error_message: Optional[str] = None
    possible_cause: Optional[str] = None
    multi_marked: bool = False
    correctas: int = 0
    incorrectas: int = 0
    sin_responder: int = 0
    multimarcadas: int = 0
    incompletas: int = 0
    responses: Dict[str, str] = Field(default_factory=dict)
    audits: List[QuestionAudit] = Field(default_factory=list)
    processed_image_url: Optional[str] = None
    original_image_url: Optional[str] = None


class ZipProcessSummary(BaseModel):
    filename: str
    status: str = "COMPLETED"  # COMPLETED, ERROR
    total_sheets: int = 0
    success_count: int = 0
    error_count: int = 0
    error_message: Optional[str] = None


class BatchProcessResponse(BaseModel):
    job_id: str
    exam_name: Optional[str] = "Examen OMR"
    status: str = "completed"
    total_files: int
    success_count: int = 0
    multi_marked_count: int = 0
    incompletas_count: int = 0
    error_count: int = 0
    average_score: float = 0.0
    highest_score: float = 0.0
    lowest_score: float = 0.0
    question_count: Optional[int] = None
    scoring_mode: Optional[str] = None
    zip_count: Optional[int] = 1
    zips_summary: Optional[List[ZipProcessSummary]] = Field(default_factory=list)
    results: List[SheetResult] = Field(default_factory=list)
    created_at: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # PENDING, PROCESSING, COMPLETED, FAILED
    total_files: int = 0
    processed_files: int = 0
    error: Optional[str] = None
    result: Optional[BatchProcessResponse] = None


class JobSummaryResponse(BaseModel):
    job_id: str
    exam_name: Optional[str] = "Examen OMR"
    status: str = "completed"
    created_at: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    question_count: Optional[int] = None
    total_files: int = 0
    success_count: int = 0
    multi_marked_count: int = 0
    incompletas_count: int = 0
    error_count: int = 0
    average_score: float = 0.0
    highest_score: float = 0.0
    lowest_score: float = 0.0
    zip_count: Optional[int] = 1
    zips_summary: Optional[List[ZipProcessSummary]] = None
    has_results: bool = True
    has_outputs: bool = True
    input_files_count: int = 0
    processed_images_count: int = 0


class ProcessedFileInfo(BaseModel):
    filename: str
    url: str
    path: str
    size_bytes: int


class JobFilesResponse(BaseModel):
    job_id: str
    total_files: int = 0
    files: List[ProcessedFileInfo] = Field(default_factory=list)

