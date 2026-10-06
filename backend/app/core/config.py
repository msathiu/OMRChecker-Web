from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "OMRChecker Web API"
    API_V1_STR: str = "/api"
    
    # Rutas base
    ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    STORAGE_DIR: Path = ROOT_DIR / "storage"
    TEMP_DIR: Path = STORAGE_DIR / "temp"
    TEMPLATES_DIR: Path = STORAGE_DIR / "templates"
    EVALUATIONS_DIR: Path = STORAGE_DIR / "evaluations"
    JOBS_DIR: Path = STORAGE_DIR / "jobs"
    USERS_DIR: Path = STORAGE_DIR / "users"
    USERS_FILE: Path = USERS_DIR / "users.json"
    SESSIONS_FILE: Path = USERS_DIR / "sessions.json"
    SAMPLES_DIR: Path = ROOT_DIR / "samples"
    
    # Reglas de examen estándar OMR
    MAX_QUESTIONS: int = 40
    STANDARD_TEMPLATE_DIR: Path = SAMPLES_DIR / "standard"
    STANDARD_TEMPLATE_PATH: Path = STANDARD_TEMPLATE_DIR / "template.json"

    # Límites para subida y procesamiento masivo (1.2 GB+ / 4,000 exámenes)
    MAX_ZIP_SIZE_BYTES: int = 3 * 1024 * 1024 * 1024  # 3 GB límite para archivo ZIP
    MAX_UNCOMPRESSED_BYTES: int = 10 * 1024 * 1024 * 1024  # 10 GB límite descomprimido
    UPLOAD_CHUNK_SIZE_BYTES: int = 1024 * 1024  # 1 MB por bloque de streaming
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    def init_storage(self):
        """Asegura que los directorios base de almacenamiento existan."""
        for path in [self.STORAGE_DIR, self.TEMP_DIR, self.TEMPLATES_DIR, self.EVALUATIONS_DIR, self.JOBS_DIR, self.USERS_DIR]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.init_storage()

