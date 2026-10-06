from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.app.schemas.auth import (
    AuthResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from backend.app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticación"])


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
            detail="Sesión inválida o expirada. Por favor inicie sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[UserResponse]:
    token = extract_token_from_header(authorization)
    if not token:
        return None
    return auth_service.get_user_by_token(token)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registro de nuevo usuario",
)
async def register(req: UserRegisterRequest):
    """
    Registra un nuevo usuario con Nombre, Correo institucional y Clave.
    """
    try:
        user = auth_service.register_user(req)
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
async def login(req: UserLoginRequest):
    """
    Inicia sesión con correo institucional y clave.
    """
    try:
        user, token = auth_service.authenticate_user(req.correo, req.clave)
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
async def logout(authorization: Optional[str] = Header(None)):
    """
    Invalida y elimina la sesión activa del usuario.
    """
    token = extract_token_from_header(authorization)
    if token:
        auth_service.invalidate_session(token)
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
