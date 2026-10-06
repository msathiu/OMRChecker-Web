import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.schemas.evaluation import (
    EvaluationDetail,
    EvaluationSummary,
    EvaluationValidateResponse,
)
from src.schemas import SCHEMA_VALIDATORS


class EvaluationService:
    def list_evaluations(self) -> List[EvaluationSummary]:
        summaries: List[EvaluationSummary] = []

        # 1. Escanear samples
        if settings.SAMPLES_DIR.exists():
            for e_path in settings.SAMPLES_DIR.rglob("evaluation.json"):
                rel_id = f"sample:{e_path.parent.relative_to(settings.SAMPLES_DIR)}"
                summary = self._build_summary(rel_id, e_path.parent.name, e_path)
                if summary:
                    summaries.append(summary)

        # 2. Escanear storage/evaluations/
        if settings.EVALUATIONS_DIR.exists():
            for e_dir in settings.EVALUATIONS_DIR.iterdir():
                e_path = e_dir / "evaluation.json"
                if e_dir.is_dir() and e_path.exists():
                    summary = self._build_summary(f"custom:{e_dir.name}", e_dir.name, e_path)
                    if summary:
                        summaries.append(summary)

        return summaries

    def get_evaluation_path(self, eval_id: str) -> Optional[Path]:
        if eval_id.startswith("sample:"):
            subpath = eval_id.replace("sample:", "")
            candidate = settings.SAMPLES_DIR / subpath / "evaluation.json"
            return candidate if candidate.exists() else None
        elif eval_id.startswith("custom:"):
            name = eval_id.replace("custom:", "")
            candidate = settings.EVALUATIONS_DIR / name / "evaluation.json"
            return candidate if candidate.exists() else None
        else:
            custom_candidate = settings.EVALUATIONS_DIR / eval_id / "evaluation.json"
            if custom_candidate.exists():
                return custom_candidate
            sample_candidate = settings.SAMPLES_DIR / eval_id / "evaluation.json"
            if sample_candidate.exists():
                return sample_candidate
            return None

    def get_evaluation_detail(self, eval_id: str) -> Optional[EvaluationDetail]:
        path = self.get_evaluation_path(eval_id)
        if not path:
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return EvaluationDetail(
            id=eval_id,
            name=path.parent.name,
            config=data,
        )

    def validate_evaluation_dict(self, data: Dict[str, Any]) -> EvaluationValidateResponse:
        validator = SCHEMA_VALIDATORS["evaluation"]
        errors = []
        for error in validator.iter_errors(data):
            path_str = ".".join(str(p) for p in error.path) if error.path else "$root"
            errors.append(f"[{path_str}]: {error.message}")

        # Validar límite estricto de preguntas (1..MAX_QUESTIONS)
        opts = data.get("options", {})
        q_list = opts.get("questions_in_order", [])
        if isinstance(q_list, list):
            from src.utils.parsing import parse_fields
            try:
                parsed_qs = parse_fields("Questions", q_list)
                if len(parsed_qs) > settings.MAX_QUESTIONS:
                    errors.append(
                        f"El número de preguntas ({len(parsed_qs)}) excede el límite máximo permitido de {settings.MAX_QUESTIONS}."
                    )
                elif len(parsed_qs) == 0:
                    errors.append("El archivo de evaluación debe contener al menos 1 pregunta.")
            except Exception:
                pass

        return EvaluationValidateResponse(valid=len(errors) == 0, errors=errors)

    def save_custom_evaluation(
        self,
        name: str,
        data: Dict[str, Any],
    ) -> EvaluationDetail:
        validation = self.validate_evaluation_dict(data)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))

        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip()
        if not safe_name:
            safe_name = "evaluation_custom"

        target_dir = settings.EVALUATIONS_DIR / safe_name
        target_dir.mkdir(parents=True, exist_ok=True)

        eval_file = target_dir / "evaluation.json"
        with eval_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        eval_id = f"custom:{safe_name}"
        return EvaluationDetail(
            id=eval_id,
            name=safe_name,
            config=data,
        )

    def _build_summary(self, eval_id: str, name: str, path: Path) -> Optional[EvaluationSummary]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            opts = data.get("options", {})
            q_list = opts.get("questions_in_order", [])
            schemes = list(data.get("marking_schemes", {}).keys())

            return EvaluationSummary(
                id=eval_id,
                name=name,
                source_type=data.get("source_type", "custom"),
                total_questions=len(q_list),
                sections=schemes,
            )
        except Exception:
            return None


evaluation_service = EvaluationService()

