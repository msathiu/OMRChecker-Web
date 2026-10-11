"""
Punto de entrada principal para el backend FastAPI de OMRChecker.
"""
# 1. Aplicar parche defensivo para servidor headless antes de importar módulos OpenCV
import backend.app.core.headless_patch  # noqa: F401

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.deps import get_current_user
from backend.app.api.routes_admin import router as admin_router
from backend.app.api.routes_auth import router as auth_router
from backend.app.api.routes_evaluations import router as evaluations_router
from backend.app.api.routes_exams import router as exams_router
from backend.app.api.routes_export import router as export_router
from backend.app.api.routes_omr import router as omr_router
from backend.app.api.routes_templates import router as templates_router
from backend.app.api.routes_users import router as users_router
from backend.app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API REST para procesamiento y evaluación de hojas OMR basada en OMRChecker.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    field_labels = {
        "nombre": "El nombre completo",
        "name": "El nombre completo",
        "correo": "El correo electrónico",
        "email": "El correo electrónico",
        "clave": "La contraseña",
        "password": "La contraseña",
        "confirmacion_clave": "La confirmación de contraseña",
        "password_confirmation": "La confirmación de contraseña",
        "role": "El rol",
    }
    formatted_errors = []
    messages = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = str(loc[-1]) if loc else ""
        err_type = err.get("type", "")
        raw_msg = str(err.get("msg", ""))

        clean_msg = raw_msg
        if clean_msg.startswith("Value error, "):
            clean_msg = clean_msg[len("Value error, "):]

        if err_type == "missing" or clean_msg.lower() == "field required":
            label = field_labels.get(field, f"El campo '{field}'" if field else "Este campo")
            formatted_msg = f"{label} es obligatorio."
        elif "string_too_short" in err_type or "at least" in clean_msg.lower():
            label = field_labels.get(field, f"El campo '{field}'" if field else "Este campo")
            formatted_msg = f"{label} no cumple con la longitud mínima requerida."
        else:
            formatted_msg = clean_msg

        err_copy = {
            "type": err.get("type", ""),
            "loc": list(err.get("loc", ())),
            "msg": formatted_msg,
            "input": err.get("input"),
        }
        formatted_errors.append(err_copy)
        messages.append(formatted_msg)

    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "detail": formatted_errors,
            "message": " ".join(messages) if messages else "Error de validación en la solicitud.",
        }),
    )

# Configurar CORS para permitir comunicación con el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length"],
)

# Registrar Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(exams_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(omr_router, prefix=settings.API_V1_STR)
app.include_router(templates_router, prefix=settings.API_V1_STR)
app.include_router(evaluations_router, prefix=settings.API_V1_STR)
app.include_router(export_router, prefix=settings.API_V1_STR)


@app.get("/api/history", tags=["OMR Jobs"])
async def history_alias(current_user=Depends(get_current_user)):
    from backend.app.api.routes_omr import get_user_exam_history
    return await get_user_exam_history(current_user)


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "engine": "OMRChecker Core (src/)",
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Bienvenido a OMRChecker Web API",
        "docs": "/docs",
        "health": "/api/health",
    }
