"""
routes_users.py - Endpoints para administración de cuentas de usuario.
Acceso exclusivo para administradores (ADMIN).
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.api.deps import require_admin, require_editor_or_admin
from backend.app.schemas.auth import (
    AuditLogResponse,
    UserCreateByAdminRequest,
    UserResponse,
    UserUpdateRequest,
)
from backend.app.services.auth_service import auth_service

router = APIRouter(prefix="/users", tags=["Administración de Usuarios"])


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "127.0.0.1"


@router.get(
    "",
    response_model=List[UserResponse],
    summary="Listar usuarios (Admin o Editor)",
)
async def list_users(
    current_user: UserResponse = Depends(require_editor_or_admin),
):
    """
    Lista usuarios registrados.
    - Si el solicitante es editor: devuelve únicamente usuarios activos con rol 'usuario' para asignación.
    - Si el solicitante es administrador: devuelve todos los usuarios.
    """
    users = auth_service.list_users()
    if current_user.role == "editor":
        return [u for u in users if u.role == "usuario" and u.is_active]
    return users


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo usuario con rol editor o usuario (Admin)",
)
async def create_user(
    req: UserCreateByAdminRequest,
    request: Request,
    admin_user: UserResponse = Depends(require_admin),
):
    """
    Permite al administrador crear una cuenta con rol 'editor' o 'usuario'.
    No permite crear administradores (los administradores solo se crean por consola).
    """
    try:
        return auth_service.create_user_by_admin(
            req=req,
            admin_user=admin_user,
            ip_address=_get_client_ip(request),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al crear el usuario: {str(e)}",
        )


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Modificar un usuario existente (Admin)",
)
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    request: Request,
    admin_user: UserResponse = Depends(require_admin),
):
    """
    Modifica datos, rol (editor o usuario) o activa/desactiva una cuenta de usuario.
    """
    try:
        return auth_service.update_user_by_admin(
            user_id=user_id,
            req=req,
            admin_user=admin_user,
            ip_address=_get_client_ip(request),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al actualizar el usuario: {str(e)}",
        )


@router.delete(
    "/{user_id}",
    summary="Eliminar una cuenta de usuario (Admin)",
)
async def delete_user(
    user_id: str,
    request: Request,
    admin_user: UserResponse = Depends(require_admin),
):
    """
    Elimina permanentemente una cuenta de usuario y revoca todas sus sesiones.
    Un administrador no puede eliminarse a sí mismo.
    """
    try:
        auth_service.delete_user_by_admin(
            user_id=user_id,
            admin_user=admin_user,
            ip_address=_get_client_ip(request),
        )
        return {"message": "Usuario eliminado exitosamente"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al eliminar el usuario: {str(e)}",
        )


@router.get(
    "/{user_id}/activity",
    response_model=List[AuditLogResponse],
    summary="Consultar registro de actividad de un usuario (Admin)",
)
async def get_user_activity(
    user_id: str,
    admin_user: UserResponse = Depends(require_admin),
):
    """
    Consulta el historial de auditoría y actividad reciente de un usuario.
    """
    return auth_service.get_user_activity(user_id)

