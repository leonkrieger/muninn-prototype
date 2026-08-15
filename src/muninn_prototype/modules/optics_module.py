from __future__ import annotations
import io
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from pathlib import Path
from pubsub import pub
from muninn_prototype.modules.base_module import BaseModule
from muninn_prototype.modules.backup_module import _configured_csv_path
from muninn_prototype.modules.command_events import COMMAND_TOPIC, load_commands

logger = logging.getLogger(__name__)

class Camera(Protocol):
    def capture_jpeg(self) -> bytes: ...
    def capture_full_res_jpeg(self, width: int, height: int) -> bytes: ...
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

    def capture_full_res_jpeg(self, width: int, height: int) -> bytes:
        output = io.BytesIO()
        still_config = self._camera.create_still_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        self._camera.switch_mode_and_capture_file(still_config, output, format="jpeg")
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

def _camera_config(configuration: dict[str, Any] | None) -> tuple[float, int, int, int, int, int]:
    config = (configuration or {}).get("optics", {})
    fps = float(config.get("feed_fps", 0.2))
    if not 0.1 <= fps <= 1.0:
        raise ValueError("optics.feed_fps must be between 0.1 and 1.0")
    width, height = int(config.get("width", 640)), int(config.get("height", 480))
    full_width = int(config.get("full_width", 4056))
    full_height = int(config.get("full_height", 3040))
    quality = int(config.get("jpeg_quality", 70))
    if min(width, height, full_width, full_height) <= 0 or not 1 <= quality <= 100:
        raise ValueError("optics dimensions must be positive and jpeg_quality must be 1..100")
    return fps, width, height, quality, full_width, full_height

class OpticsModule(BaseModule):
    def __init__(self, camera: Camera | None = None) -> None:
        super().__init__()
        self._camera, self._configured_camera = camera, camera is not None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._fps, self._width, self._height, self._frame_id = 0.2, 640, 480, 0
        self._full_width, self._full_height = 4056, 3040
        self._capture_lock = threading.Lock()
        self._images_path: Path | None = None
        self._command_subscribed = False
        self._capture_command = ""

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        super().initiate()
        self._capture_command = next(
            (event for name, event in load_commands().items() if name == "capture_full_res_photo"),
            "",
        )
        if not self._command_subscribed:
            pub.subscribe(self._on_command, COMMAND_TOPIC)
            self._command_subscribed = True
        if not (configuration or {}).get("optics", {}).get("enabled", True):
            logger.info("Optics disabled by configuration")
            return
        try:
            (
                self._fps, self._width, self._height, quality,
                self._full_width, self._full_height,
            ) = _camera_config(configuration)
            csv_path = _configured_csv_path(configuration)
            self._images_path = csv_path.parent / "images"
            if not self._configured_camera:
                self._camera = PiCamera(self._width, self._height, quality)
        except Exception as error:
            logger.error("Optics unavailable: %s", error)
            pub.sendMessage("error", message="", error_code="optics_unavailable")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="OpticsModule")
        self._thread.start()

    def _on_command(self, command: str) -> None:
        if command != self._capture_command:
            return
        try:
            self.capture_full_res_photo()
        except Exception:
            logger.exception("Failed to capture full-resolution photo")
            pub.sendMessage("status", message="photo_capture_failed")
            return
        pub.sendMessage("status", message="photo_capture_succeeded")

    def _capture_loop(self) -> None:
        assert self._camera is not None
        while not self._stop_event.is_set():
            try:
                self._frame_id += 1
                with self._capture_lock:
                    image = self._camera.capture_jpeg()
                pub.sendMessage("images", frame=ImageFrame(datetime.now(timezone.utc), image, self._width, self._height), frame_id=self._frame_id)
            except Exception:
                logger.exception("Failed to capture camera image")
            self._stop_event.wait(1.0 / self._fps)

    def capture_full_res_photo(self) -> Path:
        """Capture and store one full-resolution JPEG in the backup images folder."""
        if self._camera is None or self._images_path is None:
            raise RuntimeError("Optics module is not initialized")

        timestamp = datetime.now(timezone.utc)
        with self._capture_lock:
            image = self._camera.capture_full_res_jpeg(self._full_width, self._full_height)
        self._images_path.mkdir(parents=True, exist_ok=True)
        image_path = self._images_path / f"image-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.jpg"
        image_path.write_bytes(image)
        return image_path

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._camera is not None:
            self._camera.close()
