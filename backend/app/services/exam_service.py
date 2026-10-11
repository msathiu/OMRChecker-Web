"""
exam_service.py - Servicio para gestión y ciclo de vida de Exámenes OMR.
Controla creación, configuración de respuestas, asignación a usuarios y validación de permisos.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from backend.app.db.database import get_db, log_audit
from backend.app.schemas.auth import UserResponse
from backend.app.schemas.exam import (
    AssignedUserDetail,
    ExamAssignmentRequest,
    ExamAssignmentResponse,
    ExamCreateRequest,
    ExamResponse,
    ExamUpdateRequest,
)


class ExamService:
    @staticmethod
    def _build_evaluation_dict(
        question_count: int,
        answers: Dict[str, str],
        scoring_mode: str,
        equal_points: float,
        specific_points: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        """Construye el objeto de evaluación formal (evaluation.json) para el motor OMRChecker."""
        questions_in_order = [f"q{i}" for i in range(1, question_count + 1)]
        answers_in_order = [answers.get(str(i), "A") for i in range(1, question_count + 1)]

        marking_schemes: Dict[str, Any] = {}
        if scoring_mode == "EQUAL":
            marking_schemes["DEFAULT"] = {
                "correct": float(equal_points),
                "incorrect": 0.0,
                "unmarked": 0.0,
            }
        else:
            marking_schemes["DEFAULT"] = {
                "correct": 1.0,
                "incorrect": 0.0,
                "unmarked": 0.0,
            }
            spec = specific_points or {}
            for i in range(1, question_count + 1):
                q_key = f"q{i}"
                pts = float(spec.get(str(i), 1.0))
                marking_schemes[f"SECTION_{q_key}"] = {
                    "questions": [q_key],
                    "marking": {
                        "correct": pts,
                        "incorrect": 0.0,
                        "unmarked": 0.0,
                    },
                }

        return {
            "source_type": "custom",
            "options": {
                "questions_in_order": questions_in_order,
                "answers_in_order": answers_in_order,
                "should_explain_scoring": True,
            },
            "marking_schemes": marking_schemes,
        }

    def create_exam(
        self,
        req: ExamCreateRequest,
        creator: UserResponse,
        ip_address: Optional[str] = None,
    ) -> ExamResponse:
        """Crea un examen configurado con su clave de respuestas. Solo permitido para Editor o Admin."""
        if creator.role not in ("editor", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Los usuarios con rol 'usuario' no pueden crear ni configurar exámenes.",
            )

        exam_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        eval_dict = self._build_evaluation_dict(
            question_count=req.question_count,
            answers=req.answers,
            scoring_mode=req.scoring_mode,
            equal_points=req.equal_points,
            specific_points=req.specific_points,
        )

        enabled_users_list = req.enabled_user_ids or []
        spec_pts_json = json.dumps(req.specific_points or {})
        answers_json = json.dumps(req.answers)
        eval_json = json.dumps(eval_dict, ensure_ascii=False)
        enabled_users_json = json.dumps(enabled_users_list)

        with get_db() as conn:
            conn.execute("""
            INSERT INTO exams (
                id, name, description, creator_id, creator_name, creator_email,
                question_count, scoring_mode, equal_points, specific_points_json,
                answers_json, evaluation_json, is_active, enabled_for_all,
                enabled_users_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?);
            """, (
                exam_id,
                req.name,
                req.description,
                creator.id,
                creator.nombre,
                creator.correo,
                req.question_count,
                req.scoring_mode,
                req.equal_points,
                spec_pts_json,
                answers_json,
                eval_json,
                1 if req.enabled_for_all else 0,
                enabled_users_json,
                now,
                now,
            ))

            for uid in enabled_users_list:
                asgn_id = str(uuid.uuid4())
                conn.execute("""
                INSERT OR IGNORE INTO exam_assignments (id, exam_id, user_id, assigned_by, assigned_at, status)
                VALUES (?, ?, ?, ?, ?, 'active');
                """, (asgn_id, exam_id, uid, creator.id, now))

        log_audit(
            action="CREATE_EXAM",
            user_id=creator.id,
            user_name=creator.nombre,
            user_email=creator.correo,
            user_role=creator.role,
            target_id=exam_id,
            details={"exam_name": req.name, "question_count": req.question_count},
            ip_address=ip_address,
        )

        return ExamResponse(
            id=exam_id,
            name=req.name,
            description=req.description,
            creator_id=creator.id,
            creator_name=creator.nombre,
            creator_email=creator.correo,
            question_count=req.question_count,
            scoring_mode=req.scoring_mode,
            equal_points=req.equal_points,
            specific_points=req.specific_points,
            answers=req.answers,
            is_active=True,
            enabled_for_all=req.enabled_for_all,
            enabled_user_ids=enabled_users_list,
            assigned_count=len(enabled_users_list),
            created_at=now,
            updated_at=now,
        )

    def get_exam_by_id(self, exam_id: str, current_user: UserResponse) -> ExamResponse:
        """Obtiene los detalles del examen validando estrictamente los permisos del rol."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT e.*,
                   (SELECT count(*) FROM exam_assignments ea WHERE ea.exam_id = e.id AND ea.status = 'active') as asgn_count
            FROM exams e WHERE e.id = ?;
            """, (exam_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Examen no encontrado.")

            enabled_users: List[str] = []
            if row["enabled_users_json"]:
                try:
                    enabled_users = json.loads(row["enabled_users_json"])
                except Exception:
                    pass

            # Validar permisos por rol
            if current_user.role == "admin":
                pass
            elif current_user.role == "editor":
                if row["creator_id"] != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tienes permiso para consultar exámenes configurados por otro editor.",
                    )
            elif current_user.role == "usuario":
                cursor.execute("""
                SELECT 1 FROM exam_assignments
                WHERE exam_id = ? AND user_id = ? AND status = 'active';
                """, (exam_id, current_user.id))
                is_assigned = cursor.fetchone() is not None or (current_user.id in enabled_users)

                if not is_assigned or not bool(row["is_active"]):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Este examen no está asignado a tu cuenta de usuario.",
                    )
            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado.")

            # Para el rol 'usuario', OMITIR la clave de respuestas para proteger la pauta
            answers_dict = None
            if current_user.role in ("admin", "editor"):
                try:
                    answers_dict = json.loads(row["answers_json"])
                except Exception:
                    answers_dict = {}

            spec_points = None
            if row["specific_points_json"]:
                try:
                    spec_points = json.loads(row["specific_points_json"])
                except Exception:
                    pass

            return ExamResponse(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                creator_id=row["creator_id"],
                creator_name=row["creator_name"],
                creator_email=row["creator_email"],
                question_count=row["question_count"],
                scoring_mode=row["scoring_mode"],
                equal_points=row["equal_points"],
                specific_points=spec_points,
                answers=answers_dict,
                is_active=bool(row["is_active"]),
                enabled_for_all=bool(row["enabled_for_all"]),
                enabled_user_ids=enabled_users,
                assigned_count=row["asgn_count"] or 0,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_exams_for_user(self, current_user: UserResponse) -> List[ExamResponse]:
        """
        Retorna la lista de exámenes permitidos para el rol:
        - Admin: todos los exámenes registrados con conteo de asignaciones.
        - Editor: únicamente los exámenes creados por él con conteo de asignaciones.
        - Usuario: únicamente los exámenes asignados a él (sin clave de respuestas).
        """
        with get_db() as conn:
            cursor = conn.cursor()
            if current_user.role == "admin":
                cursor.execute("""
                SELECT e.*,
                       (SELECT count(*) FROM exam_assignments ea WHERE ea.exam_id = e.id AND ea.status = 'active') as asgn_count
                FROM exams e
                ORDER BY e.created_at DESC;
                """)
            elif current_user.role == "editor":
                cursor.execute("""
                SELECT e.*,
                       (SELECT count(*) FROM exam_assignments ea WHERE ea.exam_id = e.id AND ea.status = 'active') as asgn_count
                FROM exams e
                WHERE e.creator_id = ?
                ORDER BY e.created_at DESC;
                """, (current_user.id,))
            else:
                # Rol 'usuario': EXCLUSIVAMENTE exámenes asignados a este usuario
                cursor.execute("""
                SELECT DISTINCT e.*,
                       1 as asgn_count
                FROM exams e
                JOIN exam_assignments ea ON e.id = ea.exam_id
                WHERE ea.user_id = ? AND ea.status = 'active' AND e.is_active = 1
                ORDER BY ea.assigned_at DESC;
                """, (current_user.id,))

            rows = cursor.fetchall()
            exams: List[ExamResponse] = []

            for row in rows:
                enabled_users: List[str] = []
                if row["enabled_users_json"]:
                    try:
                        enabled_users = json.loads(row["enabled_users_json"])
                    except Exception:
                        pass

                answers_dict = None
                if current_user.role in ("admin", "editor"):
                    try:
                        answers_dict = json.loads(row["answers_json"])
                    except Exception:
                        answers_dict = {}

                spec_points = None
                if row["specific_points_json"]:
                    try:
                        spec_points = json.loads(row["specific_points_json"])
                    except Exception:
                        pass

                exams.append(ExamResponse(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    creator_id=row["creator_id"],
                    creator_name=row["creator_name"],
                    creator_email=row["creator_email"],
                    question_count=row["question_count"],
                    scoring_mode=row["scoring_mode"],
                    equal_points=row["equal_points"],
                    specific_points=spec_points,
                    answers=answers_dict,
                    is_active=bool(row["is_active"]),
                    enabled_for_all=bool(row["enabled_for_all"]),
                    enabled_user_ids=enabled_users,
                    assigned_count=row["asgn_count"] or 0,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ))

            return exams

    def update_exam(
        self,
        exam_id: str,
        req: ExamUpdateRequest,
        current_user: UserResponse,
        ip_address: Optional[str] = None,
    ) -> ExamResponse:
        """Actualiza un examen. Solo el Editor creador o el Admin pueden modificarlo."""
        if current_user.role not in ("editor", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Los usuarios con rol 'usuario' no pueden modificar exámenes ni pautas de respuestas.",
            )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Examen no encontrado.")

            if current_user.role == "editor" and row["creator_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permiso para modificar exámenes creados por otro editor.",
                )

            # Extraer valores previos y fusionar
            new_name = req.name if req.name is not None else row["name"]
            new_desc = req.description if req.description is not None else row["description"]
            new_q_count = req.question_count if req.question_count is not None else row["question_count"]
            new_mode = req.scoring_mode if req.scoring_mode is not None else row["scoring_mode"]
            new_eq_pts = req.equal_points if req.equal_points is not None else row["equal_points"]

            prev_spec = json.loads(row["specific_points_json"]) if row["specific_points_json"] else {}
            new_spec = req.specific_points if req.specific_points is not None else prev_spec

            prev_answers = json.loads(row["answers_json"]) if row["answers_json"] else {}
            new_answers = req.answers if req.answers is not None else prev_answers

            new_active = int(req.is_active) if req.is_active is not None else row["is_active"]
            new_for_all = int(req.enabled_for_all) if req.enabled_for_all is not None else row["enabled_for_all"]

            prev_users = json.loads(row["enabled_users_json"]) if row["enabled_users_json"] else []
            new_users = req.enabled_user_ids if req.enabled_user_ids is not None else prev_users

            now = datetime.now(timezone.utc).isoformat()

            # Reconstruir evaluation.json si cambiaron preguntas, respuestas o puntos
            new_eval_dict = self._build_evaluation_dict(
                question_count=new_q_count,
                answers=new_answers,
                scoring_mode=new_mode,
                equal_points=new_eq_pts,
                specific_points=new_spec,
            )

            cursor.execute("""
            UPDATE exams
            SET name = ?, description = ?, question_count = ?, scoring_mode = ?, equal_points = ?,
                specific_points_json = ?, answers_json = ?, evaluation_json = ?,
                is_active = ?, enabled_for_all = ?, enabled_users_json = ?, updated_at = ?
            WHERE id = ?;
            """, (
                new_name,
                new_desc,
                new_q_count,
                new_mode,
                new_eq_pts,
                json.dumps(new_spec),
                json.dumps(new_answers),
                json.dumps(new_eval_dict, ensure_ascii=False),
                new_active,
                new_for_all,
                json.dumps(new_users),
                now,
                exam_id,
            ))

        log_audit(
            action="UPDATE_EXAM",
            user_id=current_user.id,
            user_name=current_user.nombre,
            user_email=current_user.correo,
            user_role=current_user.role,
            target_id=exam_id,
            details={"exam_name": new_name, "updated_by": current_user.correo},
            ip_address=ip_address,
        )

        return ExamResponse(
            id=exam_id,
            name=new_name,
            description=new_desc,
            creator_id=row["creator_id"],
            creator_name=row["creator_name"],
            creator_email=row["creator_email"],
            question_count=new_q_count,
            scoring_mode=new_mode,
            equal_points=new_eq_pts,
            specific_points=new_spec,
            answers=new_answers,
            is_active=bool(new_active),
            enabled_for_all=bool(new_for_all),
            enabled_user_ids=new_users,
            created_at=row["created_at"],
            updated_at=now,
        )

    def delete_exam(
        self,
        exam_id: str,
        current_user: UserResponse,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Elimina un examen configurado. Solo el Editor creador o el Admin pueden eliminarlo."""
        if current_user.role not in ("editor", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Los usuarios con rol 'usuario' no pueden eliminar exámenes.",
            )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Examen no encontrado.")

            if current_user.role == "editor" and row["creator_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permiso para eliminar exámenes creados por otro editor.",
                )

            cursor.execute("DELETE FROM exams WHERE id = ?;", (exam_id,))

        log_audit(
            action="DELETE_EXAM",
            user_id=current_user.id,
            user_name=current_user.nombre,
            user_email=current_user.correo,
            user_role=current_user.role,
            target_id=exam_id,
            details={"deleted_exam_name": row["name"]},
            ip_address=ip_address,
        )
        return True

    def assign_exam_to_users(
        self,
        exam_id: str,
        user_ids: List[str],
        current_user: UserResponse,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Asigna un examen a uno o múltiples usuarios. Solo permitido para Editor creador o Admin."""
        if current_user.role not in ("editor", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para asignar exámenes a otros usuarios.",
            )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            exam = cursor.fetchone()
            if not exam:
                raise HTTPException(status_code=404, detail="Examen no encontrado.")

            if current_user.role == "editor" and exam["creator_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes asignar exámenes que tú hayas creado.",
                )

            now = datetime.now(timezone.utc).isoformat()
            assigned_count = 0

            # Validar que los user_ids existan y sean de rol 'usuario'
            for uid in user_ids:
                cursor.execute("SELECT id, role, is_active FROM users WHERE id = ?;", (uid,))
                u_row = cursor.fetchone()
                if not u_row:
                    continue
                if u_row["role"] != "usuario":
                    continue

                cursor.execute(
                    "SELECT id FROM exam_assignments WHERE exam_id = ? AND user_id = ?;",
                    (exam_id, uid),
                )
                existing = cursor.fetchone()
                if not existing:
                    asgn_id = str(uuid.uuid4())
                    cursor.execute("""
                    INSERT INTO exam_assignments (id, exam_id, user_id, assigned_by, assigned_at, status)
                    VALUES (?, ?, ?, ?, ?, 'active');
                    """, (asgn_id, exam_id, uid, current_user.id, now))
                    assigned_count += 1
                else:
                    cursor.execute("""
                    UPDATE exam_assignments SET status = 'active', assigned_at = ?
                    WHERE exam_id = ? AND user_id = ?;
                    """, (now, exam_id, uid))

            cursor.execute("""
            SELECT count(*) as total FROM exam_assignments
            WHERE exam_id = ? AND status = 'active';
            """, (exam_id,))
            total_row = cursor.fetchone()
            total_assigned = total_row["total"] if total_row else 0

        log_audit(
            action="ASSIGN_EXAM",
            user_id=current_user.id,
            user_name=current_user.nombre,
            user_email=current_user.correo,
            user_role=current_user.role,
            target_id=exam_id,
            details={
                "exam_name": exam["name"],
                "newly_assigned_count": assigned_count,
                "total_assigned": total_assigned,
            },
            ip_address=ip_address,
        )

        return {
            "exam_id": exam_id,
            "exam_name": exam["name"],
            "assigned_count": assigned_count,
            "total_assigned": total_assigned,
            "assigned_users": self.get_exam_assignments(exam_id, current_user),
            "message": f"Se asignaron {assigned_count} usuario(s) exitosamente.",
        }

    def get_exam_assignments(
        self,
        exam_id: str,
        current_user: UserResponse,
    ) -> List[Dict[str, Any]]:
        """Lista los usuarios asignados a un examen. Solo para Editor propietario o Admin."""
        if current_user.role not in ("editor", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para consultar las asignaciones de este examen.",
            )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            exam = cursor.fetchone()
            if not exam:
                raise HTTPException(status_code=404, detail="Examen no encontrado.")

            if current_user.role == "editor" and exam["creator_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes consultar asignaciones de tus propios exámenes.",
                )

            cursor.execute("""
            SELECT ea.id as assignment_id, ea.user_id, ea.assigned_at, ea.assigned_by, ea.status,
                   u.nombre, u.correo,
                   ab.nombre as assigned_by_name
            FROM exam_assignments ea
            JOIN users u ON ea.user_id = u.id
            LEFT JOIN users ab ON ea.assigned_by = ab.id
            WHERE ea.exam_id = ? AND ea.status = 'active'
            ORDER BY ea.assigned_at DESC;
            """, (exam_id,))
            rows = cursor.fetchall()

            return [
                {
                    "id": r["user_id"],
                    "assignment_id": r["assignment_id"],
                    "nombre": r["nombre"],
                    "correo": r["correo"],
                    "assigned_at": r["assigned_at"],
                    "assigned_by": r["assigned_by"],
                    "assigned_by_name": r["assigned_by_name"] or "Editor",
                    "status": r["status"],
                }
                for r in rows
            ]

    def unassign_user_from_exam(
        self,
        exam_id: str,
        user_id: str,
        current_user: UserResponse,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Elimina la asignación de un usuario a un examen."""
        if current_user.role not in ("editor", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para revocar asignaciones de exámenes.",
            )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            exam = cursor.fetchone()
            if not exam:
                raise HTTPException(status_code=404, detail="Examen no encontrado.")

            if current_user.role == "editor" and exam["creator_id"] != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo puedes revocar asignaciones de tus propios exámenes.",
                )

            cursor.execute("""
            DELETE FROM exam_assignments WHERE exam_id = ? AND user_id = ?;
            """, (exam_id, user_id))

        log_audit(
            action="UNASSIGN_EXAM",
            user_id=current_user.id,
            user_name=current_user.nombre,
            user_email=current_user.correo,
            user_role=current_user.role,
            target_id=exam_id,
            details={"unassigned_user_id": user_id, "exam_name": exam["name"]},
            ip_address=ip_address,
        )

        return {"message": "Asignación revocada exitosamente."}

    def get_exam_evaluation_for_processing(self, exam_id: str, current_user: UserResponse) -> tuple[str, bytes, int]:
        """
        Retorna (exam_name, evaluation_bytes, question_count) para procesar un lote OMR.
        Valida estrictamente que el usuario tenga asignado el examen para procesar.
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"El examen '{exam_id}' no existe.")

            if not bool(row["is_active"]):
                raise HTTPException(status_code=403, detail="Este examen está inactivo y no acepta cargas.")

            if current_user.role == "usuario":
                cursor.execute("""
                SELECT 1 FROM exam_assignments
                WHERE exam_id = ? AND user_id = ? AND status = 'active';
                """, (exam_id, current_user.id))
                is_assigned = cursor.fetchone() is not None
                if not is_assigned:
                    # Fallback si estaba en enabled_users_json
                    enabled_users = []
                    if row["enabled_users_json"]:
                        try:
                            enabled_users = json.loads(row["enabled_users_json"])
                        except Exception:
                            pass
                    is_assigned = current_user.id in enabled_users

                if not is_assigned:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tienes autorización para procesar este examen. No está asignado a tu cuenta.",
                    )
            elif current_user.role == "editor":
                if row["creator_id"] != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No puedes procesar exámenes creados por otro editor.",
                    )

            eval_bytes = row["evaluation_json"].encode("utf-8")
            return row["name"], eval_bytes, row["question_count"]

    get_evaluation_json_bytes_for_processing = get_exam_evaluation_for_processing

    def verify_job_access(self, job_id: str, current_user: UserResponse) -> Dict[str, Any]:
        """
        Valida que el usuario tenga permisos para acceder a un trabajo de procesamiento OMR:
        - Admin: acceso a todos los trabajos.
        - Editor: acceso a sus propios trabajos o a trabajos asociados a exámenes creados por él.
        - Usuario: acceso EXCLUSIVAMENTE a sus propios trabajos.
        """
        job_dict: Optional[Dict[str, Any]] = None
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,))
            row = cursor.fetchone()
            if row:
                job_dict = dict(row)

        if not job_dict:
            from backend.app.services.storage_service import storage_service
            paths = storage_service.get_job_paths(job_id)
            if not paths["root"].exists():
                raise HTTPException(status_code=404, detail=f"Trabajo '{job_id}' no encontrado.")
            info_p = paths["root"] / "job_info.json"
            res_p = paths["results"] / "results.json"
            if res_p.exists():
                try:
                    with res_p.open("r", encoding="utf-8") as f:
                        job_dict = json.load(f)
                except Exception:
                    pass
            elif info_p.exists():
                try:
                    with info_p.open("r", encoding="utf-8") as f:
                        job_dict = json.load(f)
                except Exception:
                    pass

        if not job_dict:
            raise HTTPException(status_code=404, detail=f"Trabajo '{job_id}' no encontrado.")

        job_user_id = job_dict.get("user_id")

        if current_user.role == "admin":
            return job_dict

        if current_user.role == "editor":
            if job_user_id == current_user.id:
                return job_dict
            exam_id = job_dict.get("exam_id")
            if exam_id:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT creator_id FROM exams WHERE id = ?;", (exam_id,))
                    ex = cursor.fetchone()
                    if ex and ex["creator_id"] == current_user.id:
                        return job_dict
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a los datos de este examen.",
            )

        if current_user.role == "usuario":
            if job_user_id == current_user.id:
                return job_dict
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a los resultados o archivos de este examen.",
            )

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado.")


exam_service = ExamService()
