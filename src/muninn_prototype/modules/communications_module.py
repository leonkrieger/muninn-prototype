from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from pubsub import pub

from muninn_prototype.modules.base_module import BaseModule

from .topic_config import topic

logger = logging.getLogger(__name__)


class CommunicationsModule(BaseModule):
    """Own the lifecycle of the external Talkkonnect Mumble client."""

    def __init__(self) -> None:
        super().__init__()
        self._process: subprocess.Popen[bytes] | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._restart_delay_s = 10.0
        self._startup_grace_s = 2.0
        self._executable = "talkkonnect"
        self._config_path = ""
        self._lock = threading.Lock()
        self._output_threads: list[threading.Thread] = []
        self._talkkonnect_log: Path | None = None

    def _command(self) -> list[str]:
        return [self._executable, "-config", self._config_path]

    def _publish_error(self, code: str, message: str) -> None:
        logger.error(message)
        pub.sendMessage(topic("errors"), message=message, error_code=code)

    def _start_process(self) -> bool:
        if not self._executable:
            self._publish_error(
                "communications_executable_missing",
                "Talkkonnect executable is not configured",
            )
            return False
        if not self._config_path or not Path(self._config_path).is_file():
            self._publish_error(
                "communications_config_missing",
                f"Talkkonnect config does not exist: {self._config_path}",
            )
            return False
        try:
            process = subprocess.Popen(
                self._command(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=os.environ.copy(),
            )
        except (OSError, ValueError) as exc:
            self._publish_error(
                "communications_start_failed", f"Failed to start Talkkonnect: {exc}"
            )
            return False
        with self._lock:
            self._process = process
        self._start_output_reader(process)
        logger.info("Started Talkkonnect (pid %s)", process.pid)
        return True

    def _start_output_reader(self, process: subprocess.Popen[bytes]) -> None:
        """Separate Talkkonnect output from Muninn terminal stream."""
        output = process.stdout
        if output is None:
            return

        def read_output() -> None:
            log_file = self._talkkonnect_log
            if log_file is not None:
                log_file.parent.mkdir(parents=True, exist_ok=True)
            with output:
                for raw_line in iter(output.readline, b""):
                    line = raw_line.decode(errors="replace").rstrip("\\r\\n")
                    if not line:
                        continue
                    logger.info("[TALKKONNECT] %s", line)
                    if log_file is not None:
                        with log_file.open("a", encoding="utf-8") as handle:
                            handle.write(line + "\\n")

        reader = threading.Thread(
            target=read_output,
            daemon=True,
            name="CommunicationsModule:TalkkonnectOutput",
        )
        self._output_threads.append(reader)
        reader.start()

    def _monitor(self) -> None:
        while not self._stop_event.is_set():
            if not self._start_process():
                self._stop_event.wait(self._restart_delay_s)
                continue
            process = self._process
            if process is None:
                continue
            return_code = process.wait()
            with self._lock:
                if self._process is process:
                    self._process = None
            if self._stop_event.is_set():
                break
            logger.warning("Talkkonnect exited with code %s", return_code)
            self._stop_event.wait(self._restart_delay_s)

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        settings = (configuration or {}).get("communications", {})
        if not bool(settings.get("enabled", True)):
            logger.info("Communications module is disabled")
            return
        self._executable = str(settings.get("executable", "talkkonnect")).strip()
        self._config_path = str(settings.get("config_path", "")).strip()
        log_path = str(settings.get("output_log", "logs/talkkonnect.log")).strip()
        self._talkkonnect_log = Path(log_path) if log_path else None
        if self._talkkonnect_log is not None and not self._talkkonnect_log.is_absolute():
            self._talkkonnect_log = Path.cwd() / self._talkkonnect_log
        self._restart_delay_s = max(0.1, float(settings.get("restart_delay_s", 10.0)))
        self._startup_grace_s = max(0.0, float(settings.get("startup_grace_s", 2.0)))
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            logger.debug("Communications worker is already running")
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor, daemon=True, name="CommunicationsModule:Talkkonnect"
        )
        self._monitor_thread.start()
        super().initiate()

    def shutdown(self) -> None:
        self._stop_event.set()
        with self._lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=max(1.0, self._startup_grace_s))
            except subprocess.TimeoutExpired:
                logger.warning("Talkkonnect did not terminate; killing it")
                process.kill()
                process.wait()
        thread = self._monitor_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self._startup_grace_s + 1.0))
        with self._lock:
            self._process = None
