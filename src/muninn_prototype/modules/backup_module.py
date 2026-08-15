from __future__ import annotations

import csv
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pubsub import pub

from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading
from muninn_prototype.utils.get_project_root import get_project_root
from muninn_prototype.modules.base_module import BaseModule
from muninn_prototype.modules.topic_config import topic
from muninn_prototype.modules.backup_retention import get_retention


logger = logging.getLogger(__name__)

_CSV_FIELDNAMES = ["reading_id", "timestamp", "sensor_name", "sensor_type", "measurement", "unit", "value", "priority"]


def _default_csv_path() -> Path:
    project_root = get_project_root(Path(__file__).resolve())
    created_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return project_root / "backups" / f"readings-{created_at}.csv"


def _configured_csv_path(configuration: dict[str, Any] | None = None) -> Path:
    configured_path = (configuration or {}).get("backup", {}).get("csv_path")
    if configured_path:
        return Path(str(configured_path)).expanduser()

    return _default_csv_path()


def _ensure_header(csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if csv_path.exists() and csv_path.stat().st_size > 0:
        return

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()


def _reading_to_row(reading: SensorReading) -> dict[str, str]:
    return {
        "reading_id": str(reading.reading_id),
        "timestamp": reading.timestamp.isoformat(),
        "sensor_name": reading.sensor_name,
        "sensor_type": reading.sensor_type,
        "measurement": reading.measurement,
        "unit": reading.unit,
        "value": str(reading.value),
        "priority": str(reading.priority),
    }


class BackupModule(BaseModule):
    def __init__(self):
        super().__init__()
        self._csv_lock = threading.Lock()
        self._csv_path: Path | None = None
        self._subscribed = False
        self._retention = None

    def _on_reading(self, reading: SensorReading) -> None:
        if self._csv_path is None or self._retention is None:
            logger.debug("Backup module is not initialized")
            return
        try:
            with self._retention.lock, self._csv_lock:
                if not self._retention.backup_enabled:
                    return
                partition = reading.timestamp.astimezone(timezone.utc).strftime("%Y%m%d")
                self._csv_path = self._csv_path.parent / f"readings-{partition}-p{reading.priority:02d}.csv"
                _ensure_header(self._csv_path)
                with self._csv_path.open("a", newline="", encoding="utf-8") as csv_file:
                    csv.DictWriter(csv_file, fieldnames=_CSV_FIELDNAMES).writerow(_reading_to_row(reading))
                self._retention.cleanup({self._csv_path})
        except Exception:
            logger.debug("Failed to write backup for reading from %s", reading.sensor_name or "unknown sensor", exc_info=True)
        else:
            logger.debug("Successfully wrote backup for reading %s from %s", reading.reading_id, reading.sensor_name or "unknown sensor")

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        self._csv_path = _configured_csv_path(configuration)
        root = self._csv_path.parent if self._csv_path.suffix.lower() == ".csv" else self._csv_path
        root.mkdir(parents=True, exist_ok=True)
        self._retention = get_retention(root, configuration)
        if not self._subscribed:
            pub.subscribe(self._on_reading, topic("readings"))
            self._subscribed = True
        super().initiate()
        logger.info("Backing up sensor readings to %s", self._csv_path)
