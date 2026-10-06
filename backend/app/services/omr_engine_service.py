"""
Servicio Adaptador del Motor OMRChecker.
Invoca directamente las clases y módulos del motor original (src/) sin modificar su código.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Aplicar parche headless antes de importar módulos de visión interactivos
import backend.app.core.headless_patch
from backend.app.core.config import settings
from backend.app.schemas.omr import (
    BatchProcessResponse,
    QuestionAudit,
    SheetResult,
)
from src.defaults import CONFIG_DEFAULTS
from src.evaluation import EvaluationConfig
from src.template import Template
from src.utils.image import ImageUtils
from src.utils.parsing import get_concatenated_response, open_config_with_defaults


def classify_detected_response(raw_val: Any) -> Tuple[str, str, int]:
    """
    Clasifica las respuestas detectadas por OMR:
    - 0 letras detectadas: ('', 'SIN RESPONDER', 0)
    - 1 letra detectada: (letra, 'NORMAL', 1) [ej. 'A', 'B', 'C', 'D', 'E']
    - 2 a 4 letras detectadas: ('MULTIMARCADA', 'MULTIMARCADA', n) [ej. 'AB', 'ACD']
    - 5 letras detectadas (ABCDE): ('INCOMPLETA', 'INCOMPLETA', 5) [regla especial: NO MULTIMARCADA]

    Retorna: (export_value, classification, letter_count)
    """
    if raw_val is None:
        return ("", "SIN RESPONDER", 0)

    val_str = str(raw_val).strip()
    # Filtrar únicamente caracteres de burbuja A-Z
    letters = [ch for ch in val_str.upper() if "A" <= ch <= "Z"]
    count = len(letters)

    if count == 0:
        return ("", "SIN RESPONDER", 0)
    elif count == 1:
        return (letters[0], "NORMAL", 1)
    elif 2 <= count <= 4:
        return ("MULTIMARCADA", "MULTIMARCADA", count)
    else:  # count >= 5 (ABCDE)
        return ("INCOMPLETA", "INCOMPLETA", count)


class OMREngineService:
    def __init__(self):
        self._default_tuning_config = deepcopy(CONFIG_DEFAULTS)
        # Asegurar parámetros seguros para servidor web
        self._default_tuning_config.outputs.show_image_level = 0
        self._default_tuning_config.outputs.save_image_level = 0
        self._default_tuning_config.outputs.save_detections = False

    def load_tuning_config(self, config_path: Optional[Path] = None):
        if config_path and config_path.exists():
            config = open_config_with_defaults(config_path)
        else:
            config = deepcopy(self._default_tuning_config)
        # Siempre forzar niveles de visualización en 0 para API
        config.outputs.show_image_level = 0
        config.outputs.save_image_level = 0
        config.outputs.save_detections = False
        return config

    def load_template(self, template_path: Path, tuning_config=None) -> Template:
        if not template_path.exists():
            raise FileNotFoundError(f"Plantilla no encontrada en: {template_path}")
        config = tuning_config or self.load_tuning_config()
        return Template(template_path, config)

    def load_evaluation(
        self,
        evaluation_path: Path,
        template: Template,
        tuning_config=None,
    ) -> EvaluationConfig:
        if not evaluation_path.exists():
            raise FileNotFoundError(f"Archivo de evaluación no encontrado en: {evaluation_path}")
        config = tuning_config or self.load_tuning_config()
        return EvaluationConfig(
            curr_dir=evaluation_path.parent,
            evaluation_path=evaluation_path,
            template=template,
            tuning_config=config,
        )

    def process_single_image(
        self,
        img_name: str,
        in_omr: np.ndarray,
        template: Template,
        tuning_config,
        evaluation_config: Optional[EvaluationConfig] = None,
        output_dir: Optional[Path] = None,
        job_id: Optional[str] = None,
    ) -> SheetResult:
        """
        Procesa una sola hoja OMR en memoria utilizando el pipeline original de OMRChecker.
        """
        # 1. Validación de imagen cargada
        orig_img_url = f"/api/omr/jobs/{job_id}/original-image/{img_name}" if job_id else None
        if in_omr is None or not isinstance(in_omr, np.ndarray) or in_omr.size == 0:
            return SheetResult(
                file_id=img_name,
                original_name=img_name,
                score=0.0,
                status="ERROR",
                error_message="No fue posible procesar esta hoja de respuestas.",
                possible_cause="La imagen está dañada, vacía o en un formato no soportado.",
                multi_marked=False,
                responses={},
                audits=[],
                processed_image_url=None,
                original_image_url=orig_img_url,
            )

        try:
            # 2. Aplicar preprocesadores (CropPage, CropOnMarkers, etc.)
            processed_img = template.image_instance_ops.apply_preprocessors(
                img_name, in_omr, template
            )

            if processed_img is None:
                return SheetResult(
                    file_id=img_name,
                    original_name=img_name,
                    score=0.0,
                    status="ERROR",
                    error_message="No fue posible detectar correctamente la hoja de respuestas.",
                    possible_cause="Los marcadores de alineamiento no fueron detectados, o la imagen está borrosa, recortada o inclinada fuera del área esperada.",
                    multi_marked=False,
                    responses={},
                    audits=[],
                    processed_image_url=None,
                    original_image_url=orig_img_url,
                )

            # 3. Leer respuestas OMR (cálculo de umbrales y burbujas)
            (
                raw_response,
                final_marked,
                multi_marked,
                _multi_roll,
            ) = template.image_instance_ops.read_omr_response(
                template,
                image=processed_img,
                name=img_name,
                save_dir=None,
            )

            # 4. Concatenar campos compuestos (Roll, preguntas multidígito, etc.)
            concatenated_response = get_concatenated_response(raw_response, template)

            # 5. Guardar imagen resultante procesada si se indicó directorio
            image_url = None
            if output_dir is not None:
                output_dir.mkdir(parents=True, exist_ok=True)
                output_image_path = output_dir / f"marked_{img_name}"
                cv2.imwrite(str(output_image_path), final_marked)
                if job_id:
                    image_url = f"/api/omr/jobs/{job_id}/image/marked_{img_name}"
        except Exception as e:
            return SheetResult(
                file_id=img_name,
                original_name=img_name,
                score=0.0,
                status="ERROR",
                error_message=f"Error durante el procesamiento OMR de la hoja: {str(e)}",
                possible_cause="Fallo en la calibración geométrica o en la segmentación de la cuadrícula de respuestas.",
                multi_marked=False,
                responses={},
                audits=[],
                processed_image_url=None,
                original_image_url=orig_img_url,
            )

        # 5. Evaluación y clasificación estandarizada de respuestas
        score = 0.0
        max_possible_score = 0.0
        audits: List[QuestionAudit] = []

        classified_responses = dict(concatenated_response)
        has_question_multi = False
        multimarcadas = 0
        incompletas = 0
        sin_responder = 0
        correctas = 0
        incorrectas = 0

        if evaluation_config is not None:
            evaluation_config.reset_explanation_table()
            current_score = 0.0

            for q in evaluation_config.questions_in_order:
                raw_ans = concatenated_response.get(q, template.global_empty_val)
                export_val, classification, letter_count = classify_detected_response(raw_ans)
                classified_responses[q] = export_val

                matcher = evaluation_config.question_to_answer_matcher[q]
                max_delta = matcher.marking.get("correct", 1.0)
                if isinstance(max_delta, (int, float)):
                    max_possible_score += max_delta

                section_name = (
                    matcher.get_section_explanation()
                    if evaluation_config.has_non_default_section
                    else None
                )

                if classification == "SIN RESPONDER":
                    sin_responder += 1
                    verdict = "SIN RESPONDER"
                    delta = float(matcher.marking.get("unmarked", 0.0))
                    marked_display = "SIN RESPONDER"
                elif classification == "MULTIMARCADA":
                    has_question_multi = True
                    multimarcadas += 1
                    incorrectas += 1
                    verdict = "MULTIMARCADA"
                    delta = float(matcher.marking.get("incorrect", 0.0))
                    marked_display = "MULTIMARCADA"
                elif classification == "INCOMPLETA":
                    incompletas += 1
                    incorrectas += 1
                    verdict = "INCOMPLETA"
                    delta = float(matcher.marking.get("incorrect", 0.0))
                    marked_display = "INCOMPLETA"
                else:  # NORMAL (1 letra detectada: A, B, C, D o E)
                    letter = export_val
                    q_verdict, q_delta = matcher.get_verdict_marking(letter)
                    delta = float(q_delta)
                    marked_display = letter
                    if q_verdict.lower().startswith("correct"):
                        verdict = "correct"
                        correctas += 1
                    else:
                        verdict = "incorrect"
                        incorrectas += 1

                current_score += delta

                audits.append(
                    QuestionAudit(
                        question=q,
                        marked=marked_display,
                        allowed_answers=str(matcher),
                        verdict=verdict,
                        delta=round(delta, 2),
                        score=round(current_score, 2),
                        section=section_name,
                    )
                )

            score = float(current_score)
        else:
            # Sin archivo de evaluación: clasificar preguntas q1..qN presentes
            for k, val in concatenated_response.items():
                if re.match(r"^q\d+$", k, re.IGNORECASE):
                    export_val, classification, _ = classify_detected_response(val)
                    classified_responses[k] = export_val
                    if classification == "MULTIMARCADA":
                        has_question_multi = True
                        multimarcadas += 1
                    elif classification == "INCOMPLETA":
                        incompletas += 1
                    elif classification == "SIN RESPONDER":
                        sin_responder += 1
                    else:
                        correctas += 1

        # 6. Calcular porcentajes y estado
        percentage = None
        if max_possible_score > 0:
            percentage = round(max(0.0, (score / max_possible_score) * 100), 1)

        # Regla: MULTIMARCADA solo cuando hay 2-4 letras marcadas (o roll multimarcado).
        # ABCDE (5 letras) es INCOMPLETA y explícitamente NO cuenta como MULTIMARCADA.
        has_multi = bool(has_question_multi or _multi_roll)
        status = "MULTI_MARKED" if has_multi else "SUCCESS"

        return SheetResult(
            file_id=img_name,
            original_name=img_name,
            score=score,
            max_score=round(max_possible_score, 2) if max_possible_score > 0 else None,
            percentage=percentage,
            status=status,
            multi_marked=has_multi,
            correctas=correctas,
            incorrectas=incorrectas,
            sin_responder=sin_responder,
            multimarcadas=multimarcadas,
            incompletas=incompletas,
            responses=classified_responses,
            audits=audits,
            processed_image_url=image_url,
            original_image_url=orig_img_url,
        )

    def process_batch(
        self,
        file_paths: List[Path],
        template_path: Path,
        evaluation_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
        job_id: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> BatchProcessResponse:
        """
        Procesa un lote de archivos (imágenes y/o PDFs) devolviendo métricas agregadas y detalle.
        """
        tuning_config = self.load_tuning_config(config_path)
        template = self.load_template(template_path, tuning_config)

        eval_config = None
        if evaluation_path and evaluation_path.exists():
            eval_config = self.load_evaluation(evaluation_path, template, tuning_config)

        results: List[SheetResult] = []

        for file_idx, file_path in enumerate(file_paths, start=1):
            try:
                # Cargar imagen(es) - ImageUtils.load_omr_image maneja PDFs multipágina nativamente
                loaded_images = ImageUtils.load_omr_image(file_path, tuning_config)
            except Exception as e:
                results.append(
                    SheetResult(
                        file_id=file_path.name,
                        original_name=file_path.name,
                        score=0.0,
                        status="ERROR",
                        error_message=f"No se pudo cargar el archivo como imagen: {str(e)}",
                        multi_marked=False,
                        responses={},
                        audits=[],
                    )
                )
                continue

            if not loaded_images:
                results.append(
                    SheetResult(
                        file_id=file_path.name,
                        original_name=file_path.name,
                        score=0.0,
                        status="ERROR",
                        error_message="No se encontraron imágenes válidas dentro del archivo.",
                        multi_marked=False,
                        responses={},
                        audits=[],
                    )
                )
                continue

            for page_index, (img_name, in_omr) in enumerate(loaded_images, start=1):
                sheet_res = self.process_single_image(
                    img_name=img_name,
                    in_omr=in_omr,
                    template=template,
                    tuning_config=tuning_config,
                    evaluation_config=eval_config,
                    output_dir=output_dir,
                    job_id=job_id,
                )
                sheet_res.page_number = page_index
                sheet_res.original_name = file_path.name
                results.append(sheet_res)

            # Liberación activa de memoria para evitar saturación (OOM) en lotes masivos de 4,000 imágenes
            del loaded_images
            if file_idx % 50 == 0:
                import gc
                gc.collect()

        # Estadísticas del lote
        success_count = sum(1 for r in results if r.status == "SUCCESS")
        multi_marked_count = sum(1 for r in results if r.status == "MULTI_MARKED")
        incompletas_count = sum(1 for r in results if r.incompletas > 0)
        error_count = sum(1 for r in results if r.status == "ERROR")

        valid_scores = [r.score for r in results if r.status != "ERROR"]
        avg_score = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0
        high_score = max(valid_scores) if valid_scores else 0.0
        low_score = min(valid_scores) if valid_scores else 0.0

        return BatchProcessResponse(
            job_id=job_id or "local",
            status="completed_with_errors" if error_count > 0 else "completed",
            total_files=len(results),
            success_count=success_count,
            multi_marked_count=multi_marked_count,
            incompletas_count=incompletas_count,
            error_count=error_count,
            average_score=avg_score,
            highest_score=high_score,
            lowest_score=low_score,
            results=results,
            created_at=datetime.utcnow().isoformat(),
        )


omr_engine_service = OMREngineService()

