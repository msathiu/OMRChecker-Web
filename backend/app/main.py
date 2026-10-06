"""
Punto de entrada principal para el backend FastAPI de OMRChecker.
"""
# 1. Aplicar parche defensivo para servidor headless antes de importar módulos OpenCV
import backend.app.core.headless_patch  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes_auth import router as auth_router
from backend.app.api.routes_evaluations import router as evaluations_router
from backend.app.api.routes_export import router as export_router
from backend.app.api.routes_omr import router as omr_router
from backend.app.api.routes_templates import router as templates_router
from backend.app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API REST para procesamiento y evaluación de hojas OMR basada en OMRChecker.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configurar CORS para permitir comunicación con el futuro frontend en React
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
app.include_router(omr_router, prefix=settings.API_V1_STR)
app.include_router(templates_router, prefix=settings.API_V1_STR)
app.include_router(evaluations_router, prefix=settings.API_V1_STR)
app.include_router(export_router, prefix=settings.API_V1_STR)


@app.get("/api/history", tags=["OMR Jobs"])
@app.get("/api/exams", tags=["OMR Jobs"])
async def history_alias(current_user=None):
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

