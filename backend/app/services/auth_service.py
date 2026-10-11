"""
auth_service.py - Servicio de autenticación, control de sesiones, roles y auditoría.
Utiliza almacenamiento relacional en SQLite con sincronización defensiva en users.json y sessions.json.
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import settings
from backend.app.db.database import get_db, init_db, log_audit
from backend.app.schemas.auth import (
    AuditLogResponse,
    UserCreateByAdminRequest,
    UserRegisterRequest,
    UserResponse,
    UserUpdateRequest,
)


class AuthService:
    def __init__(self):
        init_db()

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        ).hex()
        return f"{salt}${pwd_hash}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            salt, expected_hash = stored_hash.split("$", 1)
            calculated_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                100000,
            ).hex()
            return secrets.compare_digest(calculated_hash, expected_hash)
        except Exception:
            return False

    def _sync_json_files(self):
        """Mantiene sincronizados los archivos legacy users.json y sessions.json."""
        try:
            with get_db() as conn:
                users_rows = conn.execute("SELECT * FROM users;").fetchall()
                users_dict = {}
                for r in users_rows:
                    users_dict[r["id"]] = {
                        "id": r["id"],
                        "nombre": r["nombre"],
                        "correo": r["correo"],
                        "password_hash": r["password_hash"],
                        "role": r["role"],
                        "is_active": bool(r["is_active"]),
                        "created_at": r["created_at"],
                    }

                sessions_rows = conn.execute("""
                    SELECT s.token, s.created_at, u.id as user_id, u.correo, u.nombre, u.role
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id;
                """).fetchall()
                sessions_dict = {}
                for s in sessions_rows:
                    sessions_dict[s["token"]] = {
                        "user_id": s["user_id"],
                        "correo": s["correo"],
                        "nombre": s["nombre"],
                        "role": s["role"],
                        "created_at": s["created_at"],
                    }

            tmp_users = settings.USERS_FILE.with_suffix(".tmp")
            with tmp_users.open("w", encoding="utf-8") as f:
                json.dump(users_dict, f, indent=2, ensure_ascii=False)
            tmp_users.replace(settings.USERS_FILE)

            tmp_sess = settings.SESSIONS_FILE.with_suffix(".tmp")
            with tmp_sess.open("w", encoding="utf-8") as f:
                json.dump(sessions_dict, f, indent=2, ensure_ascii=False)
            tmp_sess.replace(settings.SESSIONS_FILE)
        except Exception as e:
            print(f"[Sync Warning] Error al sincronizar json files: {e}")

    # ==========================================
    # COMANDO CONSOLA: CREACIÓN DE ADMINISTRADOR
    # ==========================================
    def create_admin_cli(self, nombre: str, correo: str, clave: str) -> UserResponse:
        """
        Crea o actualiza de manera exclusiva el rol 'admin' desde la consola / CLI del backend.
        No existe ningún endpoint público o API que permita invocar esta función.
        """
        clean_name = nombre.strip()
        clean_email = correo.strip().lower()
        if not clean_name:
            raise ValueError("El nombre del administrador no puede estar vacío.")
        if not clean_email or "@" not in clean_email:
            raise ValueError("El correo del administrador no tiene un formato válido.")
        if not clave or len(clave) < 6:
            raise ValueError("La clave del administrador debe tener al menos 6 caracteres.")

        now = datetime.now(timezone.utc).isoformat()
        pwd_hash = self._hash_password(clave)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE correo = ? COLLATE NOCASE;", (clean_email,))
            existing = cursor.fetchone()

            if existing:
                admin_id = existing["id"]
                cursor.execute("""
                UPDATE users
                SET nombre = ?, password_hash = ?, role = 'admin', is_active = 1, updated_at = ?
                WHERE id = ?;
                """, (clean_name, pwd_hash, now, admin_id))
            else:
                admin_id = str(uuid.uuid4())
                cursor.execute("""
                INSERT INTO users (id, nombre, correo, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'admin', 1, ?, ?);
                """, (admin_id, clean_name, clean_email, pwd_hash, now, now))

        self._sync_json_files()
        log_audit(
            action="CREATE_ADMIN_CLI",
            user_id=admin_id,
            user_name=clean_name,
            user_email=clean_email,
            user_role="admin",
            target_id=admin_id,
            details={"origen": "Consola Backend CLI"},
        )

        return UserResponse(
            id=admin_id,
            nombre=clean_name,
            correo=clean_email,
            role="admin",
            is_active=True,
            created_at=now,
        )

    # ==========================================
    # REGISTRO Y AUTENTICACIÓN
    # ==========================================
    def register_user(self, req: UserRegisterRequest, ip_address: Optional[str] = None) -> UserResponse:
        """
        Registra un usuario desde la API.
        REGLA DE SEGURIDAD ESTRICTA: Jamás permite asignar el rol 'admin' por API.
        """
        email_clean = req.correo.strip().lower()
        role_raw = (req.role or "estudiante").strip().lower()

        if role_raw == "admin":
            raise ValueError("No está permitido crear administradores mediante la API. El rol administrador sólo puede crearse por consola.")

        if role_raw in ("profesor", "editor"):
            role_to_assign = "profesor"
        elif role_raw in ("estudiante", "usuario"):
            role_to_assign = "estudiante"
        else:
            role_to_assign = "estudiante"

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE correo = ? COLLATE NOCASE;", (email_clean,))
            if cursor.fetchone():
                raise ValueError("Ya existe un usuario registrado con este correo institucional.")

            user_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            pwd_hash = self._hash_password(req.clave)

            cursor.execute("""
            INSERT INTO users (id, nombre, correo, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?);
            """, (user_id, req.nombre.strip(), email_clean, pwd_hash, role_to_assign, now, now))

        self._sync_json_files()
        log_audit(
            action="REGISTER",
            user_id=user_id,
            user_name=req.nombre.strip(),
            user_email=email_clean,
            user_role=role_to_assign,
            target_id=user_id,
            details={"role": role_to_assign},
            ip_address=ip_address,
        )

        return UserResponse(
            id=user_id,
            nombre=req.nombre.strip(),
            correo=email_clean,
            role=role_to_assign,
            is_active=True,
            created_at=now,
        )

    def authenticate_user(self, correo: str, clave: str, ip_address: Optional[str] = None) -> Tuple[UserResponse, str]:
        email_clean = correo.strip().lower()

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE correo = ? COLLATE NOCASE;", (email_clean,))
            user_row = cursor.fetchone()

            if not user_row:
                log_audit(action="LOGIN_FAILED_UNKNOWN_EMAIL", user_email=email_clean, ip_address=ip_address)
                raise ValueError("Credenciales incorrectas. Verifique su correo institucional y clave.")

            if not self._verify_password(clave, user_row["password_hash"]):
                log_audit(action="LOGIN_FAILED_BAD_PASSWORD", user_id=user_row["id"], user_email=email_clean, ip_address=ip_address)
                raise ValueError("Credenciales incorrectas. Verifique su correo institucional y clave.")

            if user_row["is_active"] == 0:
                log_audit(action="LOGIN_BLOCKED_INACTIVE", user_id=user_row["id"], user_email=email_clean, user_role=user_row["role"], ip_address=ip_address)
                raise ValueError("Tu cuenta ha sido desactivada por el administrador. Contacta al soporte institucional.")

            # Generar token de sesión seguro
            token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc).isoformat()

            cursor.execute("""
            INSERT INTO sessions (token, user_id, created_at)
            VALUES (?, ?, ?);
            """, (token, user_row["id"], now))

        self._sync_json_files()
        log_audit(
            action="LOGIN",
            user_id=user_row["id"],
            user_name=user_row["nombre"],
            user_email=user_row["correo"],
            user_role=user_row["role"],
            ip_address=ip_address,
        )

        user_resp = UserResponse(
            id=user_row["id"],
            nombre=user_row["nombre"],
            correo=user_row["correo"],
            role=user_row["role"],
            is_active=bool(user_row["is_active"]),
            created_at=user_row["created_at"],
        )
        return user_resp, token

    def get_user_by_token(self, token: str) -> Optional[UserResponse]:
        if not token:
            return None

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT u.*
            FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.token = ? AND u.is_active = 1;
            """, (token,))
            row = cursor.fetchone()
            if not row:
                return None

            return UserResponse(
                id=row["id"],
                nombre=row["nombre"],
                correo=row["correo"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
            )

    def invalidate_session(self, token: str, ip_address: Optional[str] = None) -> bool:
        if not token:
            return False

        user = self.get_user_by_token(token)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sessions WHERE token = ?;", (token,))
            deleted = cursor.rowcount > 0

        if deleted:
            self._sync_json_files()
            if user:
                log_audit(
                    action="LOGOUT",
                    user_id=user.id,
                    user_name=user.nombre,
                    user_email=user.correo,
                    user_role=user.role,
                    ip_address=ip_address,
                )
        return deleted

    # ==========================================
    # GESTIÓN DE USUARIOS (ROL ADMIN)
    # ==========================================
    def list_users(self) -> List[UserResponse]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC;")
            rows = cursor.fetchall()
            return [
                UserResponse(
                    id=r["id"],
                    nombre=r["nombre"],
                    correo=r["correo"],
                    role=r["role"],
                    is_active=bool(r["is_active"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def create_user_by_admin(
        self,
        req: UserCreateByAdminRequest,
        admin_user: UserResponse,
        ip_address: Optional[str] = None,
    ) -> UserResponse:
        """El administrador crea una cuenta con rol 'profesor' o 'estudiante'. Jamás admin por API."""
        role_raw = (req.role or "estudiante").strip().lower()
        if role_raw == "admin":
            raise ValueError("No está permitido crear administradores mediante la API. El rol administrador sólo puede crearse por consola.")

        if role_raw in ("profesor", "editor"):
            assigned_role = "profesor"
        elif role_raw in ("estudiante", "usuario"):
            assigned_role = "estudiante"
        else:
            assigned_role = "estudiante"

        email_clean = req.correo.strip().lower()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE correo = ? COLLATE NOCASE;", (email_clean,))
            if cursor.fetchone():
                raise ValueError("Ya existe un usuario registrado con este correo institucional.")

            user_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            pwd_hash = self._hash_password(req.clave)

            cursor.execute("""
            INSERT INTO users (id, nombre, correo, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?);
            """, (user_id, req.nombre.strip(), email_clean, pwd_hash, assigned_role, now, now))

        self._sync_json_files()
        log_audit(
            action="CREATE_USER_BY_ADMIN",
            user_id=admin_user.id,
            user_name=admin_user.nombre,
            user_email=admin_user.correo,
            user_role="admin",
            target_id=user_id,
            details={"created_user_email": email_clean, "assigned_role": assigned_role},
            ip_address=ip_address,
        )

        return UserResponse(
            id=user_id,
            nombre=req.nombre.strip(),
            correo=email_clean,
            role=assigned_role,
            is_active=True,
            created_at=now,
        )

    def update_user_by_admin(
        self,
        user_id: str,
        req: UserUpdateRequest,
        admin_user: UserResponse,
        ip_address: Optional[str] = None,
    ) -> UserResponse:
        """Modifica datos, rol o estado activo de un usuario."""
        if req.role == "admin":
            raise ValueError("No está permitido asignar el rol administrador mediante la API.")

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                raise ValueError("Usuario no encontrado.")

            # Un administrador no puede desactivar o cambiar su propio rol accidentalmente
            if user_id == admin_user.id:
                if req.is_active is False:
                    raise ValueError("No puedes desactivar tu propia cuenta de administrador.")
                if req.role and req.role != "admin":
                    raise ValueError("No puedes degradar el rol de tu propia cuenta de administrador.")

            new_name = req.nombre.strip() if req.nombre is not None else user_row["nombre"]
            new_email = req.correo.strip().lower() if req.correo is not None else user_row["correo"]
            
            if req.role is not None:
                r_clean = req.role.strip().lower()
                if r_clean in ("profesor", "editor"):
                    new_role = "profesor"
                elif r_clean in ("estudiante", "usuario"):
                    new_role = "estudiante"
                else:
                    new_role = user_row["role"]
            else:
                new_role = user_row["role"]

            new_active = int(req.is_active) if req.is_active is not None else user_row["is_active"]
            now = datetime.now(timezone.utc).isoformat()

            # Verificar colisión de correo si cambia
            if new_email != user_row["correo"]:
                cursor.execute("SELECT id FROM users WHERE correo = ? COLLATE NOCASE AND id != ?;", (new_email, user_id))
                if cursor.fetchone():
                    raise ValueError("El correo especificado ya pertenece a otro usuario registrado.")

            cursor.execute("""
            UPDATE users
            SET nombre = ?, correo = ?, role = ?, is_active = ?, updated_at = ?
            WHERE id = ?;
            """, (new_name, new_email, new_role, new_active, now, user_id))

            # Si el usuario fue desactivado, invalidar todas sus sesiones activas de inmediato
            if new_active == 0:
                cursor.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))

        self._sync_json_files()
        log_audit(
            action="UPDATE_USER_BY_ADMIN",
            user_id=admin_user.id,
            user_name=admin_user.nombre,
            user_email=admin_user.correo,
            user_role="admin",
            target_id=user_id,
            details={"new_name": new_name, "new_email": new_email, "new_role": new_role, "new_active": bool(new_active)},
            ip_address=ip_address,
        )

        return UserResponse(
            id=user_id,
            nombre=new_name,
            correo=new_email,
            role=new_role,
            is_active=bool(new_active),
            created_at=user_row["created_at"],
        )

    def delete_user_by_admin(
        self,
        user_id: str,
        admin_user: UserResponse,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Elimina un usuario y revoca todas sus sesiones activas."""
        if user_id == admin_user.id:
            raise ValueError("No puedes eliminar tu propia cuenta de administrador.")

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                raise ValueError("Usuario no encontrado.")

            # Eliminar sesiones y usuario
            cursor.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = ?;", (user_id,))

        self._sync_json_files()
        log_audit(
            action="DELETE_USER_BY_ADMIN",
            user_id=admin_user.id,
            user_name=admin_user.nombre,
            user_email=admin_user.correo,
            user_role="admin",
            target_id=user_id,
            details={"deleted_user_email": user_row["correo"], "deleted_user_role": user_row["role"]},
            ip_address=ip_address,
        )
        return True

    def get_user_activity(self, user_id: str) -> List[AuditLogResponse]:
        """Recupera la actividad registrada para un usuario específico (para el Admin)."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM audit_logs
            WHERE user_id = ? OR target_id = ?
            ORDER BY timestamp DESC
            LIMIT 100;
            """, (user_id, user_id))
            rows = cursor.fetchall()
            activity: List[AuditLogResponse] = []
            for r in rows:
                details = None
                if r["details_json"]:
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        pass
                activity.append(AuditLogResponse(
                    id=r["id"],
                    timestamp=r["timestamp"],
                    user_id=r["user_id"],
                    user_name=r["user_name"],
                    user_email=r["user_email"],
                    user_role=r["user_role"],
                    action=r["action"],
                    target_id=r["target_id"],
                    details=details,
                    ip_address=r["ip_address"],
                ))
            return activity

    def get_system_stats(self) -> Dict[str, Any]:
        """Calcula estadísticas consolidadas del sistema para el panel del Administrador."""
        with get_db() as conn:
            cursor = conn.cursor()

            # Usuarios
            cursor.execute("SELECT role, is_active, COUNT(*) as count FROM users GROUP BY role, is_active;")
            user_group = cursor.fetchall()
            total_users = sum(r["count"] for r in user_group)
            users_by_role = {"admin": 0, "profesor": 0, "estudiante": 0, "editor": 0, "usuario": 0}
            active_users = 0
            inactive_users = 0
            for r in user_group:
                role_val = r["role"]
                norm_role = "profesor" if role_val in ("profesor", "editor") else ("estudiante" if role_val in ("estudiante", "usuario") else role_val)
                users_by_role[norm_role] = users_by_role.get(norm_role, 0) + r["count"]
                if r["is_active"]:
                    active_users += r["count"]
                else:
                    inactive_users += r["count"]

            users_by_role["editor"] = users_by_role.get("profesor", 0)
            users_by_role["usuario"] = users_by_role.get("estudiante", 0)

            # Exámenes
            cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active FROM exams;")
            exam_row = cursor.fetchone()
            total_exams = exam_row["total"] if exam_row else 0
            active_exams = exam_row["active"] if exam_row and exam_row["active"] is not None else 0

            # Cargas / Trabajos (Jobs)
            cursor.execute("""
            SELECT 
                COUNT(*) as total_jobs,
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_jobs,
                SUM(CASE WHEN status='completed_with_errors' THEN 1 ELSE 0 END) as jobs_with_errors,
                SUM(total_files) as total_sheets,
                SUM(success_count) as total_success,
                SUM(multi_marked_count) as total_multi_marked,
                SUM(error_count) as total_errors
            FROM jobs;
            """)
            jobs_row = cursor.fetchone()
            total_jobs = jobs_row["total_jobs"] if jobs_row else 0
            completed_jobs = jobs_row["completed_jobs"] if jobs_row and jobs_row["completed_jobs"] is not None else 0
            jobs_with_errors = jobs_row["jobs_with_errors"] if jobs_row and jobs_row["jobs_with_errors"] is not None else 0
            total_sheets = jobs_row["total_sheets"] if jobs_row and jobs_row["total_sheets"] is not None else 0
            total_success = jobs_row["total_success"] if jobs_row and jobs_row["total_success"] is not None else 0
            total_multi_marked = jobs_row["total_multi_marked"] if jobs_row and jobs_row["total_multi_marked"] is not None else 0
            total_errors = jobs_row["total_errors"] if jobs_row and jobs_row["total_errors"] is not None else 0

            # Actividad reciente
            cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 15;")
            recent_rows = cursor.fetchall()
            recent_activity = []
            for r in recent_rows:
                details = None
                if r["details_json"]:
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        pass
                recent_activity.append({
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "user_id": r["user_id"],
                    "user_name": r["user_name"],
                    "user_email": r["user_email"],
                    "user_role": r["user_role"],
                    "action": r["action"],
                    "target_id": r["target_id"],
                    "details": details,
                    "ip_address": r["ip_address"],
                })

            return {
                "users": {
                    "total": total_users,
                    "by_role": users_by_role,
                    "active": active_users,
                    "inactive": inactive_users,
                },
                "exams": {
                    "total": total_exams,
                    "active": active_exams,
                },
                "jobs": {
                    "total": total_jobs,
                    "completed": completed_jobs,
                    "with_errors": jobs_with_errors,
                },
                "sheets": {
                    "total": total_sheets,
                    "success": total_success,
                    "multi_marked": total_multi_marked,
                    "errors": total_errors,
                },
                "recent_activity": recent_activity,
            }

    def get_all_audit_logs(self, limit: int = 200) -> List[AuditLogResponse]:
        """Obtiene el historial completo de auditoría para el Administrador."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            logs: List[AuditLogResponse] = []
            for r in rows:
                details = None
                if r["details_json"]:
                    try:
                        details = json.loads(r["details_json"])
                    except Exception:
                        pass
                logs.append(AuditLogResponse(
                    id=r["id"],
                    timestamp=r["timestamp"],
                    user_id=r["user_id"],
                    user_name=r["user_name"],
                    user_email=r["user_email"],
                    user_role=r["user_role"],
                    action=r["action"],
                    target_id=r["target_id"],
                    details=details,
                    ip_address=r["ip_address"],
                ))
            return logs


auth_service = AuthService()
