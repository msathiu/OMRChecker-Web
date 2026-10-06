# ==============================================================================
# Dockerfile para Backend FastAPI + Motor OMRChecker
# ==============================================================================

# Imagen base ligera con Python 3.12 compatible con OMRChecker, PyMuPDF, Pandas y OpenCV
FROM python:3.12-slim

# Optimizar comportamiento de Python en contenedor
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    MPLCONFIGDIR=/tmp/matplotlib \
    PORT=8000

WORKDIR /app

# Instalar dependencias esenciales de sistema (curl requerido para HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Definir argumentos de usuario/grupo (por defecto 1000 para mapear con usuario del host)
ARG UID=1000
ARG GID=1000

# Crear usuario y grupo no-root para ejecución con privilegios mínimos
RUN addgroup --system --gid ${GID} appgroup && \
    adduser --system --uid ${UID} --gid ${GID} --home /app appuser

# Copiar archivos de dependencias
COPY requirements.txt /app/requirements.txt
COPY backend/requirements.txt /app/backend/requirements.txt

# Instalar dependencias Python verificadas (sin paquetes innecesarios)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Copiar el código del motor OMR (src), la API (backend), main.py y samples
COPY src/ /app/src/
COPY backend/ /app/backend/
COPY samples/ /app/samples/
COPY main.py /app/main.py

# Crear estructura inicial de storage y caché de matplotlib con permisos adecuados
RUN mkdir -p /app/storage/jobs \
             /app/storage/templates \
             /app/storage/evaluations \
             /app/storage/temp \
             /tmp/matplotlib && \
    chown -R appuser:appgroup /app /tmp/matplotlib && \
    chmod -R 775 /app/storage /tmp/matplotlib

# Cambiar a usuario no-root
USER appuser

# Exponer puerto HTTP de FastAPI
EXPOSE 8000

# Monitoreo de salud del contenedor
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Iniciar servidor ASGI Uvicorn con timeouts extendidos para cargas masivas (600s)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "600", "--timeout-graceful-shutdown", "600"]

