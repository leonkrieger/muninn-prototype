from __future__ import annotations
import io
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from pubsub import pub
from muninn_prototype.modules.base_module import BaseModule

logger = logging.getLogger(__name__)

class Camera(Protocol):
    def capture_jpeg(self) -> bytes: ...
    def close(self) -> None: ...

class PiCamera:
    def __init__(self, width: int, height: int, quality: int) -> None:
        from picamera2 import Picamera2
        self._camera = Picamera2()
        self._camera.configure(self._camera.create_still_configuration(
            main={"size": (width, height), "format": "RGB888"}))
        self._camera.start()
        self._quality = quality

    def capture_jpeg(self) -> bytes:
        output = io.BytesIO()
        self._camera.capture_file(output, format="jpeg")
        return output.getvalue()

    def close(self) -> None:
        self._camera.stop()
        self._camera.close()

@dataclass(frozen=True, slots=True)
class ImageFrame:
    timestamp: datetime
    image: bytes
    width: int
    height: int
    format: str = "jpeg"

def _camera_config(configuration: dict[str, Any] | None) -> tuple[float, int, int, int]:
    config = (configuration or {}).get("optics", {})
    fps = float(config.get("feed_fps", 0.2))
    if not 0.1 <= fps <= 1.0:
        raise ValueError("optics.feed_fps must be between 0.1 and 1.0")
    width, height = int(config.get("width", 640)), int(config.get("height", 480))
    quality = int(config.get("jpeg_quality", 70))
    if width <= 0 or height <= 0 or not 1 <= quality <= 100:
        raise ValueError("optics dimensions must be positive and jpeg_quality must be 1..100")
    return fps, width, height, quality

class OpticsModule(BaseModule):
    def __init__(self, camera: Camera | None = None) -> None:
        super().__init__()
        self._camera, self._configured_camera = camera, camera is not None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._fps, self._width, self._height, self._frame_id = 0.2, 640, 480, 0

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        super().initiate()
        if not (configuration or {}).get("optics", {}).get("enabled", True):
            logger.info("Optics disabled by configuration")
            return
        try:
            self._fps, self._width, self._height, quality = _camera_config(configuration)
            if not self._configured_camera:
                self._camera = PiCamera(self._width, self._height, quality)
        except Exception as error:
            logger.error("Optics unavailable: %s", error)
            pub.sendMessage("error", message="", error_code="optics_unavailable")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="OpticsModule")
        self._thread.start()

    def _capture_loop(self) -> None:
        assert self._camera is not None
        while not self._stop_event.is_set():
            try:
                self._frame_id += 1
                pub.sendMessage("images", frame=ImageFrame(datetime.now(timezone.utc), self._camera.capture_jpeg(), self._width, self._height), frame_id=self._frame_id)
            except Exception:
                logger.exception("Failed to capture camera image")
            self._stop_event.wait(1.0 / self._fps)

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._camera is not None:
            self._camera.close()
