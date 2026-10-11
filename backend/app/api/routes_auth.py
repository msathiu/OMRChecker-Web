from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from backend.app.api.deps import (
    extract_token_from_header,
    get_current_user,
    get_current_user_optional,
)
from backend.app.schemas.auth import (
    AuthResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from backend.app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "127.0.0.1"


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registro de nuevo usuario",
)
async def register(req: UserRegisterRequest, request: Request):
    """
    Registra un nuevo usuario con Nombre, Correo institucional y Clave.
    Por seguridad estricta, no permite registrar usuarios con rol administrador.
    """
    try:
        user = auth_service.register_user(req, ip_address=_get_client_ip(request))
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al registrar el usuario: {str(e)}",
        )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Inicio de sesión",
)
async def login(req: UserLoginRequest, request: Request):
    """
    Inicia sesión con correo institucional y clave.
    """
    try:
        user, token = auth_service.authenticate_user(
            req.correo,
            req.clave,
            ip_address=_get_client_ip(request),
        )
        return AuthResponse(
            token=token,
            user=user,
            message="Inicio de sesión exitoso",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno durante la autenticación: {str(e)}",
        )


@router.post(
    "/logout",
    summary="Cierre de sesión",
)
async def logout(request: Request, authorization: Optional[str] = Header(None)):
    """
    Invalida y elimina la sesión activa del usuario.
    """
    token = extract_token_from_header(authorization)
    if token:
        auth_service.invalidate_session(token, ip_address=_get_client_ip(request))
    return {"message": "Sesión cerrada exitosamente"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener usuario en sesión",
)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """
    Devuelve los datos del usuario autenticado en la sesión actual.
    """
    return current_user
