import shutil
import uuid
from pathlib import Path
from typing import Dict, Optional
from fastapi import UploadFile
from backend.app.core.config import settings


class StorageService:
    @staticmethod
    def generate_job_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def get_job_paths(job_id: str) -> Dict[str, Path]:
        job_dir = settings.JOBS_DIR / job_id
        return {
            "root": job_dir,
            "inputs": job_dir / "inputs",
            "outputs": job_dir / "outputs",
            "results": job_dir / "results",
        }

    @staticmethod
    def create_job_workspace(job_id: Optional[str] = None) -> tuple[str, Dict[str, Path]]:
        if not job_id:
            job_id = StorageService.generate_job_id()
        paths = StorageService.get_job_paths(job_id)
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        return job_id, paths

    @staticmethod
    async def save_upload(upload_file: UploadFile, destination_path: Path) -> Path:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with destination_path.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return destination_path

    @staticmethod
    def remove_job_workspace(job_id: str):
        job_dir = settings.JOBS_DIR / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

    @staticmethod
    def extract_zip_safely(
        zip_path: Path,
        destination_dir: Path,
        max_uncompressed_bytes: Optional[int] = None,
    ) -> None:
        """
        Extrae un archivo ZIP de manera segura en destination_dir.
        Previene Zip Slip (path traversal), enlaces simbólicos maliciosos y Zip Bombs.
        Soporta archivos masivos (hasta 10 GB descomprimidos).
        """
        import os
        import zipfile

        if max_uncompressed_bytes is None:
            max_uncompressed_bytes = settings.MAX_UNCOMPRESSED_BYTES

        if not zip_path.exists():
            raise FileNotFoundError(f"Archivo ZIP no encontrado en: {zip_path}")

        if not zipfile.is_zipfile(zip_path):
            raise ValueError("El archivo subido no es un archivo ZIP válido o está dañado.")

        dest_resolved = destination_dir.resolve()
        dest_resolved.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                bad_file = zf.testzip()
                if bad_file:
                    raise ValueError(f"El archivo ZIP contiene datos corruptos en '{bad_file}'.")

                members = zf.infolist()
                if not members:
                    raise ValueError("El archivo ZIP está vacío (no contiene archivos).")

                # 1. Validación previa de seguridad sobre todas las entradas
                total_uncompressed = 0
                for member in members:
                    # Enlaces simbólicos (Unix file mode 0o120000)
                    is_symlink = (member.external_attr >> 16) & 0o120000 == 0o120000
                    if is_symlink:
                        raise ValueError(
                            f"Entrada ZIP no permitida (enlace simbólico detectado): '{member.filename}'"
                        )

                    total_uncompressed += member.file_size
                    if total_uncompressed > max_uncompressed_bytes:
                        raise ValueError(
                            f"El contenido descomprimido del ZIP excede el límite permitido ({max_uncompressed_bytes // (1024 * 1024)} MB)."
                        )

                    # Validación de Zip Slip / Path Traversal
                    target_path = (dest_resolved / member.filename).resolve()
                    try:
                        target_path.relative_to(dest_resolved)
                    except ValueError:
                        raise ValueError(
                            f"Ruta maliciosa detectada en archivo ZIP (Zip Slip): '{member.filename}'"
                        )

                    if os.path.commonpath([str(dest_resolved), str(target_path)]) != str(dest_resolved):
                        raise ValueError(
                            f"Ruta fuera del directorio destino detectada en archivo ZIP: '{member.filename}'"
                        )

                # 2. Extracción de entradas validadas
                for member in members:
                    target_path = (dest_resolved / member.filename).resolve()
                    if member.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, target_path.open("wb") as dst:
                            shutil.copyfileobj(src, dst, length=1024 * 1024)

        except zipfile.BadZipFile as e:
            raise ValueError(f"Archivo ZIP corrupto o ilegible: {str(e)}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Error al descomprimir el archivo ZIP: {str(e)}")

    @staticmethod
    def get_valid_input_images(inputs_dir: Path) -> tuple[list[Path], Optional[Path]]:
        """
        Escanea recursivamente el directorio de entradas, seleccionando archivos de imagen compatibles.
        Ignora metadatos de sistema (.DS_Store, __MACOSX, ._*), archivos no soportados y extrae
        el marcador de calibración omr_marker.jpg si se encuentra presente dentro del ZIP.
        """
        allowed_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp", ".pdf"}
        valid_images: list[Path] = []
        marker_path: Optional[Path] = None

        if not inputs_dir.exists():
            return [], None

        for file_path in sorted(inputs_dir.rglob("*")):
            if not file_path.is_file():
                continue

            # Ignorar archivos ocultos o metadatos de macOS
            if file_path.name.startswith(".") or any(part.startswith("__MACOSX") for part in file_path.parts):
                continue

            ext = file_path.suffix.lower()
            if ext in allowed_extensions:
                # Separar el marcador de calibración para que no sea calificado como examen
                if file_path.name.lower() in {"omr_marker.jpg", "omr_marker.png", "omr_marker.jpeg"}:
                    if marker_path is None:
                        marker_path = file_path
                    continue

                valid_images.append(file_path)

        return valid_images, marker_path


storage_service = StorageService()

