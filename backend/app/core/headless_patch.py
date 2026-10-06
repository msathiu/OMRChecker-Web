"""
Parche defensivo para entornos sin pantalla (headless / servidores / Docker).
Evita excepciones de screeninfo y llamadas bloqueantes a ventanas de OpenCV (cv2.imshow).
"""
from dataclasses import dataclass
import cv2
import screeninfo


@dataclass
class FallbackMonitor:
    width: int = 1920
    height: int = 1080
    x: int = 0
    y: int = 0


def apply_headless_patch():
    # 1. Asegurar que screeninfo.get_monitors() nunca falle
    original_get_monitors = getattr(screeninfo, "get_monitors", None)

    def safe_get_monitors():
        try:
            monitors = original_get_monitors() if original_get_monitors else []
            if monitors:
                return monitors
        except Exception:
            pass
        return [FallbackMonitor()]

    screeninfo.get_monitors = safe_get_monitors

    # 2. Desactivar ventanas interactivas de OpenCV para el servidor web
    def noop(*args, **kwargs):
        return None

    def safe_wait_key(*args, **kwargs):
        return ord("q")

    cv2.imshow = noop
    cv2.namedWindow = noop
    cv2.moveWindow = noop
    cv2.destroyAllWindows = noop
    cv2.waitKey = safe_wait_key


# Aplicar el parche inmediatamente al importar este módulo
apply_headless_patch()

