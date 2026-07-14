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


logger = logging.getLogger(__name__)

_CSV_LOCK = threading.Lock()
_CSV_PATH: Path | None = None
_SUBSCRIBED = False

_CSV_FIELDNAMES = ["reading_id", "timestamp", "sensor_name", "sensor_type", "measurement", "unit", "value"]


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
    }


def _on_reading(reading: SensorReading) -> None:
    if _CSV_PATH is None:
        logger.debug("Failed to write backup for %s because the backup module is not initialized", reading.sensor_name or "unknown sensor")
        return

    row = _reading_to_row(reading)

    try:
        with _CSV_LOCK:
            _ensure_header(_CSV_PATH)
            with _CSV_PATH.open("a", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=_CSV_FIELDNAMES)
                writer.writerow(row)
    except Exception:
        logger.debug("Failed to write backup for reading from %s", reading.sensor_name or "unknown sensor", exc_info=True)
    else:
        logger.debug("Successfully wrote backup for reading %s from %s", reading.reading_id, reading.sensor_name or "unknown sensor")


def initiate(configuration: dict[str, Any] | None = None) -> None:
    global _CSV_PATH, _SUBSCRIBED

    _CSV_PATH = _configured_csv_path(configuration)

    if not _SUBSCRIBED:
        pub.subscribe(_on_reading, "readings")
        _SUBSCRIBED = True

    logger.debug("Started backup module; writing sensor readings to %s", _CSV_PATH)
    logger.info("Backing up sensor readings to %s", _CSV_PATH)