import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from backend.app.core.config import settings
from backend.app.schemas.auth import UserRegisterRequest, UserResponse


class AuthService:
    def __init__(self):
        self.users_file: Path = settings.USERS_FILE
        self.sessions_file: Path = settings.SESSIONS_FILE
        self._ensure_storage()

    def _ensure_storage(self):
        settings.USERS_DIR.mkdir(parents=True, exist_ok=True)
        if not self.users_file.exists():
            with self.users_file.open("w", encoding="utf-8") as f:
                json.dump({}, f)
        if not self.sessions_file.exists():
            with self.sessions_file.open("w", encoding="utf-8") as f:
                json.dump({}, f)

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

    def _load_users(self) -> Dict[str, dict]:
        if not self.users_file.exists():
            return {}
        try:
            with self.users_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_users(self, users: Dict[str, dict]):
        temp_file = self.users_file.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.users_file)

    def _load_sessions(self) -> Dict[str, dict]:
        if not self.sessions_file.exists():
            return {}
        try:
            with self.sessions_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_sessions(self, sessions: Dict[str, dict]):
        temp_file = self.sessions_file.with_suffix(".tmp")
        with temp_file.open("w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
        temp_file.replace(self.sessions_file)

    def register_user(self, req: UserRegisterRequest) -> UserResponse:
        users = self._load_users()

        # Comprobar unicidad de correo institucional
        email_clean = req.correo.strip().lower()
        for u in users.values():
            if u.get("correo", "").strip().lower() == email_clean:
                raise ValueError("Ya existe un usuario registrado con este correo institucional.")

        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        pwd_hash = self._hash_password(req.clave)

        user_data = {
            "id": user_id,
            "nombre": req.nombre.strip(),
            "correo": email_clean,
            "password_hash": pwd_hash,
            "created_at": created_at,
        }

        users[user_id] = user_data
        self._save_users(users)

        return UserResponse(
            id=user_id,
            nombre=user_data["nombre"],
            correo=user_data["correo"],
            created_at=user_data["created_at"],
        )

    def authenticate_user(self, correo: str, clave: str) -> Tuple[UserResponse, str]:
        users = self._load_users()
        email_clean = correo.strip().lower()

        found_user = None
        for u in users.values():
            if u.get("correo", "").strip().lower() == email_clean:
                found_user = u
                break

        if not found_user:
            raise ValueError("Credenciales incorrectas. Verifique su correo institucional y clave.")

        if not self._verify_password(clave, found_user.get("password_hash", "")):
            raise ValueError("Credenciales incorrectas. Verifique su correo institucional y clave.")

        # Generar token de sesión seguro
        token = secrets.token_urlsafe(32)
        sessions = self._load_sessions()

        sessions[token] = {
            "user_id": found_user["id"],
            "correo": found_user["correo"],
            "nombre": found_user["nombre"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_sessions(sessions)

        user_resp = UserResponse(
            id=found_user["id"],
            nombre=found_user["nombre"],
            correo=found_user["correo"],
            created_at=found_user["created_at"],
        )
        return user_resp, token

    def get_user_by_token(self, token: str) -> Optional[UserResponse]:
        if not token:
            return None
        sessions = self._load_sessions()
        session_data = sessions.get(token)
        if not session_data:
            return None

        users = self._load_users()
        user_data = users.get(session_data.get("user_id"))
        if not user_data:
            return None

        return UserResponse(
            id=user_data["id"],
            nombre=user_data["nombre"],
            correo=user_data["correo"],
            created_at=user_data["created_at"],
        )

    def invalidate_session(self, token: str) -> bool:
        if not token:
            return False
        sessions = self._load_sessions()
        if token in sessions:
            del sessions[token]
            self._save_sessions(sessions)
            return True
        return False


auth_service = AuthService()
