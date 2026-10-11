import re
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserRegisterRequest(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre completo del usuario")
    correo: str = Field(..., min_length=1, description="Correo electrónico institucional")
    clave: str = Field(..., min_length=4, description="Contraseña de acceso")
    confirmacion_clave: str = Field(..., min_length=4, description="Confirmación de contraseña")
    role: Optional[str] = Field("estudiante", description="Rol de usuario: estudiante o profesor (admin prohibido por API)")

    @field_validator("role")
    @classmethod
    def validate_register_role(cls, v: Optional[str]) -> str:
        if not v:
            return "estudiante"
        clean = v.strip().lower()
        if clean == "admin":
            raise ValueError("No está permitido crear administradores mediante la API. El rol administrador sólo puede crearse por consola.")
        if clean in ("profesor", "editor"):
            return "profesor"
        if clean in ("estudiante", "usuario"):
            return "estudiante"
        raise ValueError("Rol no válido. Solo se permite 'profesor' o 'estudiante'.")

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
    role: str = "estudiante"
    is_active: bool = True
    created_at: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
    message: str = "Autenticación exitosa"


class UserCreateByAdminRequest(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre completo del usuario")
    correo: str = Field(..., min_length=1, description="Correo electrónico institucional")
    clave: str = Field(..., min_length=6, description="Contraseña de acceso")
    confirmacion_clave: Optional[str] = Field(None, description="Confirmación de contraseña opcional")
    role: str = Field("estudiante", description="Rol asignado: profesor o estudiante (admin solo por consola)")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "nombre" not in d and "name" in d:
                d["nombre"] = d["name"]
            if "correo" not in d and "email" in d:
                d["correo"] = d["email"]
            if "clave" not in d and "password" in d:
                d["clave"] = d["password"]
            if "confirmacion_clave" not in d and "password_confirmation" in d:
                d["confirmacion_clave"] = d["password_confirmation"]
            if "confirmacion_clave" not in d and "confirmPassword" in d:
                d["confirmacion_clave"] = d["confirmPassword"]
            return d
        return data

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
        if not clean or not EMAIL_REGEX.match(clean):
            raise ValueError("El correo no tiene un formato válido.")
        return clean

    @field_validator("clave")
    @classmethod
    def validate_clave(cls, v: str) -> str:
        if not v or len(v.strip()) < 6:
            raise ValueError("La clave debe tener al menos 6 caracteres.")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean == "admin":
            raise ValueError("No está permitido crear administradores mediante la API. El rol administrador sólo puede crearse por consola.")
        if clean in ("profesor", "editor"):
            return "profesor"
        if clean in ("estudiante", "usuario"):
            return "estudiante"
        raise ValueError("Rol no válido. Solo se permite 'profesor' o 'estudiante'.")

    @field_validator("confirmacion_clave")
    @classmethod
    def validate_confirmacion(cls, v: Optional[str], info) -> Optional[str]:
        if v is not None and v.strip() != "":
            clave = info.data.get("clave")
            if clave and v != clave:
                raise ValueError("La clave y su confirmación no coinciden.")
        return v


class UserUpdateRequest(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        clean = v.strip().lower()
        if clean == "admin":
            raise ValueError("No está permitido asignar el rol administrador mediante la API.")
        if clean in ("profesor", "editor"):
            return "profesor"
        if clean in ("estudiante", "usuario"):
            return "estudiante"
        raise ValueError("Rol no válido. Solo se permite 'profesor' o 'estudiante'.")

    @field_validator("correo")
    @classmethod
    def validate_correo(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("El correo no tiene un formato válido.")
        return clean


class AuditLogResponse(BaseModel):
    id: str
    timestamp: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    action: str
    target_id: Optional[str] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
