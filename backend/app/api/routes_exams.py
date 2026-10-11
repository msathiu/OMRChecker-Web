"""
routes_exams.py - Endpoints API para gestión del ciclo de vida de Exámenes OMR.
Permite a Editores y Administradores crear, consultar, actualizar y eliminar exámenes y pautas de evaluación.
Permite a Usuarios consultar los exámenes habilitados para ellos (sin exponer la clave de respuestas).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.app.api.deps import get_current_user, require_editor_or_admin
from backend.app.schemas.auth import UserResponse
from backend.app.schemas.exam import (
    AssignedUserDetail,
    ExamAssignmentRequest,
    ExamAssignmentResponse,
    ExamCreateRequest,
    ExamResponse,
    ExamUpdateRequest,
)
from backend.app.services.exam_service import exam_service

router = APIRouter(prefix="/exams", tags=["Exámenes"])


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "127.0.0.1"


@router.post(
    "",
    response_model=ExamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo examen (Editor o Admin)",
)
async def create_exam(
    req: ExamCreateRequest,
    request: Request,
    current_user: UserResponse = Depends(require_editor_or_admin),
):
    """
    Crea un nuevo examen con su configuración de respuestas correctas,
    modalidad de puntuación y asignación de usuarios permitidos.
    Solo accesible para roles 'editor' y 'admin'.
    """
    try:
        return exam_service.create_exam(
            req=req,
            creator=current_user,
            ip_address=_get_client_ip(request),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al crear el examen: {str(e)}",
        )


@router.get(
    "",
    response_model=List[ExamResponse],
    summary="Listar exámenes disponibles según el rol",
)
async def list_exams(
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Lista los exámenes según el rol del usuario autenticado:
    - Admin: todos los exámenes registrados en el sistema.
    - Editor: sus propios exámenes creados.
    - Usuario: los exámenes activos que le han sido asignados o habilitados para todos.
    """
    return exam_service.list_exams_for_user(current_user)


@router.get(
    "/{exam_id}",
    response_model=ExamResponse,
    summary="Obtener detalles de un examen",
)
async def get_exam(
    exam_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Obtiene los detalles y configuración de un examen específico.
    Si el solicitante es de rol 'usuario', la clave de respuestas se oculta.
    """
    return exam_service.get_exam_by_id(exam_id, current_user)


@router.put(
    "/{exam_id}",
    response_model=ExamResponse,
    summary="Actualizar un examen existente (Editor creador o Admin)",
)
async def update_exam(
    exam_id: str,
    req: ExamUpdateRequest,
    request: Request,
    current_user: UserResponse = Depends(require_editor_or_admin),
):
    """
    Modifica la configuración de un examen existente: nombre, respuestas correctas,
    puntuación, cantidad de preguntas o asignación de usuarios.
    """
    try:
        return exam_service.update_exam(
            exam_id=exam_id,
            req=req,
            current_user=current_user,
            ip_address=_get_client_ip(request),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al actualizar el examen: {str(e)}",
        )


@router.delete(
    "/{exam_id}",
    summary="Eliminar un examen (Editor creador o Admin)",
)
async def delete_exam(
    exam_id: str,
    request: Request,
    current_user: UserResponse = Depends(require_editor_or_admin),
):
    """
    Elimina un examen del sistema. Solo permitido para el editor propietario o administradores.
    """
    try:
        exam_service.delete_exam(
            exam_id=exam_id,
            current_user=current_user,
            ip_address=_get_client_ip(request),
        )
        return {"message": "Examen eliminado exitosamente"}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al eliminar el examen: {str(e)}",
        )


@router.post(
    "/{exam_id}/assign",
    response_model=ExamAssignmentResponse,
    summary="Asignar examen a usuarios (Editor propietario o Admin)",
)
async def assign_exam_to_users(
    exam_id: str,
    req: ExamAssignmentRequest,
    request: Request,
    current_user: UserResponse = Depends(require_editor_or_admin),
):
    """
    Asigna un examen existente a uno o múltiples usuarios con rol 'usuario'.
    Permite gestionar el acceso sin requerir la carga de archivos ZIP.
    """
    try:
        return exam_service.assign_exam_to_users(
            exam_id=exam_id,
            user_ids=req.user_ids,
            current_user=current_user,
            ip_address=_get_client_ip(request),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al asignar usuarios: {str(e)}",
        )


@router.get(
    "/{exam_id}/assignments",
    response_model=List[AssignedUserDetail],
    summary="Listar usuarios asignados a un examen (Editor propietario o Admin)",
)
async def get_exam_assignments(
    exam_id: str,
    current_user: UserResponse = Depends(require_editor_or_admin),
):
    """
    Obtiene la lista de usuarios actualmente asignados al examen.
    """
    try:
        return exam_service.get_exam_assignments(
            exam_id=exam_id,
            current_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al consultar asignaciones: {str(e)}",
        )


@router.delete(
    "/{exam_id}/assignments/{user_id}",
    summary="Desasignar un usuario de un examen (Editor propietario o Admin)",
)
async def unassign_user_from_exam(
    exam_id: str,
    user_id: str,
    request: Request,
    current_user: UserResponse = Depends(require_editor_or_admin),
):
    """
    Revoca la asignación de un usuario sobre el examen especificado.
    """
    try:
        exam_service.unassign_user_from_exam(
            exam_id=exam_id,
            user_id=user_id,
            current_user=current_user,
            ip_address=_get_client_ip(request),
        )
        return {"message": "Asignación revocada exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al revocar asignación: {str(e)}",
        )


