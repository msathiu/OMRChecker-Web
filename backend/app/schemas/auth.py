import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserRegisterRequest(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre completo del usuario")
    correo: str = Field(..., min_length=1, description="Correo electrónico institucional")
    clave: str = Field(..., min_length=4, description="Contraseña de acceso")
    confirmacion_clave: str = Field(..., min_length=4, description="Confirmación de contraseña")

    @field_validator("nombre")
    @classmethod
    def validate_nombre(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("El nombre no puede estar vacío.")
        return clean

    @field_validator("correo")
    @classmethod
    def validate_correo(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("El correo institucional no puede estar vacío.")
        if not EMAIL_REGEX.match(clean):
            raise ValueError("El correo institucional no tiene un formato válido.")
        return clean

    @field_validator("clave")
    @classmethod
    def validate_clave(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La clave no puede estar vacía.")
        return v

    @field_validator("confirmacion_clave")
    @classmethod
    def validate_confirmacion(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError("La confirmación de clave no puede estar vacía.")
        clave = info.data.get("clave")
        if clave and v != clave:
            raise ValueError("La clave y su confirmación no coinciden.")
        return v


class UserLoginRequest(BaseModel):
    correo: str = Field(..., min_length=1, description="Correo electrónico institucional")
    clave: str = Field(..., min_length=1, description="Contraseña de acceso")

    @field_validator("correo")
    @classmethod
    def validate_correo(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("El correo no puede estar vacío.")
        if not EMAIL_REGEX.match(clean):
            raise ValueError("El correo no tiene un formato válido.")
        return clean

    @field_validator("clave")
    @classmethod
    def validate_clave(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("La clave no puede estar vacía.")
        return v


class UserResponse(BaseModel):
    id: str
    nombre: str
    correo: str
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
    message: str = "Autenticación exitosa"
