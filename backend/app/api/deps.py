"""
deps.py - Dependencias de autenticación y autorización para FastAPI.
Valida tokens de sesión, estados de activación y roles de usuario.
"""

from typing import List, Optional
from fastapi import Depends, Header, HTTPException, status

from backend.app.schemas.auth import UserResponse
from backend.app.services.auth_service import auth_service


def extract_token_from_header(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    elif len(parts) == 1:
        return parts[0]
    return None


async def get_current_user(authorization: Optional[str] = Header(None)) -> UserResponse:
    token = extract_token_from_header(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó token de autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = auth_service.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida, expirada o cuenta desactivada. Por favor inicie sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[UserResponse]:
    token = extract_token_from_header(authorization)
    if not token:
        return None
    return auth_service.get_user_by_token(token)


ROLE_ALIASES = {
    "profesor": {"profesor", "editor"},
    "editor": {"profesor", "editor"},
    "estudiante": {"estudiante", "usuario"},
    "usuario": {"estudiante", "usuario"},
    "admin": {"admin"},
}


def require_roles(*allowed_roles: str):
    """Generador de dependencias para validar que el usuario tenga uno de los roles permitidos."""
    expanded_roles = set()
    for role in allowed_roles:
        expanded_roles.update(ROLE_ALIASES.get(role, {role}))

    async def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        user_role = current_user.role
        if user_role not in expanded_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: se requiere rol {' o '.join(allowed_roles)}. Tu rol actual es '{user_role}'.",
            )
        return current_user
    return role_checker


require_admin = require_roles("admin")
require_profesor_or_admin = require_roles("profesor", "admin")
require_editor_or_admin = require_profesor_or_admin
require_profesor = require_roles("profesor")
require_editor = require_profesor
require_estudiante = require_roles("estudiante")


