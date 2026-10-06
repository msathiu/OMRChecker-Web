# OMRChecker Web

Aplicación web para el procesamiento y evaluación automática de exámenes de selección múltiple mediante reconocimiento óptico de marcas (OMR).

> **Nota de atribución:** este proyecto utiliza como base tecnológica el proyecto **OMRChecker**. Sobre esa base se desarrollaron y adaptaron componentes propios para integrarlo en una arquitectura web con FastAPI, Docker, procesamiento mediante API, gestión de trabajos, resultados estructurados y exportación de resultados.
>
> El código original de OMRChecker conserva sus avisos de licencia y atribución correspondientes. Los componentes y modificaciones desarrollados específicamente para este proyecto se encuentran en este repositorio.

## Características

- Procesamiento de hojas de respuestas mediante OMR.
- Integración del motor OMRChecker con FastAPI.
- API REST para procesar exámenes y consultar resultados.
- Gestión de trabajos (`jobs`) y archivos procesados.
- Resultados en JSON.
- Exportación a CSV y Excel.
- Imágenes procesadas con las marcas detectadas.
- Configuración de plantillas y claves de respuestas.
- Docker y Docker Compose.
- Documentación automática de la API mediante Swagger/OpenAPI.
- Preparado para adaptar el formato de examen de hasta 40 preguntas y opciones A–E.

## Arquitectura

```text
Frontend (React + Vite)
        │
        ▼
FastAPI
        │
        ▼
OMREngineService
        │
        ▼
OMRChecker
        │
        ├── Imágenes procesadas
        ├── Resultados JSON
        ├── CSV
        └── Excel
```

## Estructura principal

```text
OMRChecker-Web/
├── backend/
├── frontend/
├── src/                    # Base OMRChecker
├── samples/                # Ejemplos
├── inputs/
├── outputs/
├── storage/
│   └── jobs/
├── main.py
├── omr_service.py
├── docker-compose.yml
├── requirements.txt
├── requirements.dev.txt
├── pyproject.toml
└── README.md
```

## Requisitos

- Linux/Ubuntu recomendado
- Python 3
- Git
- Docker
- Docker Compose

## Instalación local

Clonar el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd OMRChecker-Web
```

Crear y activar el entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Ejecutar con Docker

Desde la raíz del proyecto:

```bash
docker compose up --build
```

Para detener los servicios:

```bash
docker compose down
```

El backend estará disponible en:

```text
http://localhost:8000
```

## Swagger / API

Documentación interactiva:

```text
http://localhost:8000/docs
```

OpenAPI:

```text
http://localhost:8000/openapi.json
```

### Endpoints principales

```text
POST /api/omr/process
GET  /api/omr/jobs/{job_id}
GET  /api/omr/jobs/{job_id}/results
GET  /api/omr/jobs/{job_id}/files
GET  /api/omr/jobs/{job_id}/image/{filename}
GET  /api/omr/jobs/{job_id}/export/csv
GET  /api/omr/jobs/{job_id}/export/excel
GET  /api/export/{job_id}/json
GET  /api/health
```

También existen endpoints para administrar y validar plantillas y evaluaciones.

## Procesamiento

Los trabajos se almacenan de forma independiente:

```text
storage/jobs/{job_id}/
├── inputs/
├── outputs/
└── results/
```

Esto permite mantener separados los archivos y resultados de cada procesamiento.

## Ejemplos

El proyecto conserva ejemplos de OMRChecker en:

```text
samples/
```

Por ejemplo:

```text
samples/sample1/
├── config.json
├── template.json
├── omr_marker.jpg
└── MobileCamera/
    └── sheet1.jpg
```

Estos ejemplos se utilizan para validar que la integración web mantenga el comportamiento del motor OMR original.

## Pruebas

Ejecutar:

```bash
pytest
```

También se recomienda comprobar la aplicación dentro de Docker:

```bash
docker compose up --build
```

y verificar:

```text
http://localhost:8000/api/health
```

## Desarrollo del formato de examen

El proyecto está siendo adaptado a un formato de examen de:

- Hasta 40 preguntas.
- 5 opciones por pregunta: A, B, C, D y E.
- Una respuesta por pregunta.
- 4 marcadores de referencia OMR.
- Campos de identificación separados de las regiones OMR.

La configuración de plantilla debe conservar la alineación y el procesamiento del motor OMRChecker.

## Datos que NO deben subirse al repositorio

No subir:

- Exámenes reales con datos personales.
- Fotografías de estudiantes.
- Cédulas/identificaciones.
- Resultados reales.
- Archivos ZIP de grandes volúmenes.
- Contraseñas o claves.
- Archivos `.env`.
- Entornos virtuales.

## Licencia y atribución

Este repositorio incorpora código basado en OMRChecker.

El código original debe conservar su licencia, avisos de copyright y atribuciones correspondientes. Antes de distribuir el proyecto, consulte los archivos `LICENSE` y `README` heredados de OMRChecker y mantenga sus condiciones.

Los componentes desarrollados específicamente para la integración web se encuentran bajo las condiciones indicadas por este repositorio.

## Estado del proyecto

Actualmente el proyecto cuenta con:

- Motor OMRChecker integrado.
- Servicio `OMREngineService`.
- API FastAPI.
- Endpoints de procesamiento y resultados.
- Exportación JSON/CSV/Excel.
- Docker Compose.
- Swagger/OpenAPI.
- Ejemplos de OMRChecker disponibles dentro del contenedor.

En desarrollo:

- Integración completa del frontend React.
- Adaptación final al formato de 40 preguntas A–E.
- Pruebas con lotes ZIP grandes.
- Persistencia con PostgreSQL.
- Configuración de producción y Nginx.

## Autoría del desarrollo

Proyecto de integración y adaptación web desarrollado por **Maeva Puente**.

La base OMR/OMRChecker se mantiene identificada y atribuida de acuerdo con su proyecto y licencia original.
