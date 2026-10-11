"""
routes_admin.py - Endpoints de estadísticas globales y registro de auditoría.
Acceso exclusivo para administradores (ADMIN).
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends

from backend.app.api.deps import require_admin
from backend.app.schemas.auth import AuditLogResponse, UserResponse
from backend.app.services.auth_service import auth_service

router = APIRouter(prefix="/admin", tags=["Panel de Administración"])


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    summary="Estadísticas consolidadas del sistema (Admin)",
)
async def get_system_stats(
    admin_user: UserResponse = Depends(require_admin),
):
    """
    Retorna métricas globales del sistema:
    - Usuarios (totales, activos, desglose por rol).
    - Exámenes (totales, activos).
    - Cargas/Jobs (totales, completadas, con errores).
    - Hojas procesadas (totales, exitosas, multimarcadas, errores).
    - Actividad reciente.
    """
    return auth_service.get_system_stats()


@router.get(
    "/audit-logs",
    response_model=List[AuditLogResponse],
    summary="Historial global de auditoría (Admin)",
)
async def get_audit_logs(
    limit: int = 200,
    admin_user: UserResponse = Depends(require_admin),
):
    """
    Retorna los registros de auditoría del sistema ordenados cronológicamente.
    """
    return auth_service.get_all_audit_logs(limit=limit)

