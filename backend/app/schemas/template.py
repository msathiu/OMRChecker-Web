from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TemplateSummary(BaseModel):
    id: str
    name: str
    source: str  # "sample" o "custom"
    page_dimensions: Optional[List[int]] = None
    bubble_dimensions: Optional[List[int]] = None
    field_blocks_count: int = 0
    has_marker: bool = False
    output_columns: List[str] = Field(default_factory=list)


class TemplateDetail(BaseModel):
    id: str
    name: str
    source: str
    config: Dict[str, Any]
    has_marker: bool = False
    marker_url: Optional[str] = None


class TemplateCreateRequest(BaseModel):
    name: str
    config: Dict[str, Any]


class TemplateValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

