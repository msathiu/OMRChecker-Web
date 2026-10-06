import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.schemas.template import (
    TemplateDetail,
    TemplateSummary,
    TemplateValidateResponse,
)
from src.schemas import SCHEMA_VALIDATORS
from src.utils.file import load_json


class TemplateService:
    def list_templates(self) -> List[TemplateSummary]:
        summaries: List[TemplateSummary] = []

        # 1. Escanear samples oficiales
        if settings.SAMPLES_DIR.exists():
            for t_path in settings.SAMPLES_DIR.rglob("template.json"):
                rel_id = f"sample:{t_path.parent.relative_to(settings.SAMPLES_DIR)}"
                summary = self._build_summary(rel_id, t_path.parent.name, t_path, source="sample")
                if summary:
                    summaries.append(summary)

        # 2. Escanear plantillas creadas por usuarios en storage/templates/
        if settings.TEMPLATES_DIR.exists():
            for t_dir in settings.TEMPLATES_DIR.iterdir():
                t_path = t_dir / "template.json"
                if t_dir.is_dir() and t_path.exists():
                    summary = self._build_summary(f"custom:{t_dir.name}", t_dir.name, t_path, source="custom")
                    if summary:
                        summaries.append(summary)

        return summaries

    def get_template_path(self, template_id: str) -> Optional[Path]:
        if template_id.startswith("sample:"):
            subpath = template_id.replace("sample:", "")
            candidate = settings.SAMPLES_DIR / subpath / "template.json"
            return candidate if candidate.exists() else None
        elif template_id.startswith("custom:"):
            name = template_id.replace("custom:", "")
            candidate = settings.TEMPLATES_DIR / name / "template.json"
            return candidate if candidate.exists() else None
        else:
            # Búsqueda directa por nombre en templates o samples
            custom_candidate = settings.TEMPLATES_DIR / template_id / "template.json"
            if custom_candidate.exists():
                return custom_candidate
            sample_candidate = settings.SAMPLES_DIR / template_id / "template.json"
            if sample_candidate.exists():
                return sample_candidate
            return None

    def get_template_detail(self, template_id: str) -> Optional[TemplateDetail]:
        path = self.get_template_path(template_id)
        if not path:
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        has_marker = (path.parent / "omr_marker.jpg").exists()
        source = "sample" if template_id.startswith("sample:") else "custom"

        return TemplateDetail(
            id=template_id,
            name=path.parent.name,
            source=source,
            config=data,
            has_marker=has_marker,
            marker_url=f"/api/templates/{template_id}/marker" if has_marker else None,
        )

    def validate_template_dict(self, data: Dict[str, Any]) -> TemplateValidateResponse:
        validator = SCHEMA_VALIDATORS["template"]
        errors = []
        for error in validator.iter_errors(data):
            path_str = ".".join(str(p) for p in error.path) if error.path else "$root"
            errors.append(f"[{path_str}]: {error.message}")

        return TemplateValidateResponse(valid=len(errors) == 0, errors=errors)

    def save_custom_template(
        self,
        name: str,
        data: Dict[str, Any],
        marker_bytes: Optional[bytes] = None,
    ) -> TemplateDetail:
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip()
        if not safe_name:
            safe_name = "template_custom"

        target_dir = settings.TEMPLATES_DIR / safe_name
        target_dir.mkdir(parents=True, exist_ok=True)

        template_file = target_dir / "template.json"
        with template_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        has_marker = False
        if marker_bytes:
            marker_file = target_dir / "omr_marker.jpg"
            with marker_file.open("wb") as f:
                f.write(marker_bytes)
            has_marker = True

        template_id = f"custom:{safe_name}"
        return TemplateDetail(
            id=template_id,
            name=safe_name,
            source="custom",
            config=data,
            has_marker=has_marker,
            marker_url=f"/api/templates/{template_id}/marker" if has_marker else None,
        )

    def _build_summary(self, template_id: str, name: str, path: Path, source: str) -> Optional[TemplateSummary]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return TemplateSummary(
                id=template_id,
                name=name,
                source=source,
                page_dimensions=data.get("pageDimensions"),
                bubble_dimensions=data.get("bubbleDimensions"),
                field_blocks_count=len(data.get("fieldBlocks", {})),
                has_marker=(path.parent / "omr_marker.jpg").exists(),
                output_columns=data.get("outputColumns", []),
            )
        except Exception:
            return None


template_service = TemplateService()

