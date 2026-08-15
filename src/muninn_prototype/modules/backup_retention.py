from __future__ import annotations

import json
import csv
import logging
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    policy: str = "keep_newest"
    high_watermark_percent: float = 90.0
    low_watermark_percent: float = 80.0
    minimum_free_bytes: int = 104857600
    feed_priority: int = 80
    full_resolution_priority: int = 40
    prune_every: int = 2


@dataclass(frozen=True, slots=True)
class Artifact:
    path: Path
    created_at: float
    priority: int
    companions: tuple[Path, ...] = ()


def load_retention_config(configuration: dict[str, Any] | None) -> RetentionConfig:
    settings = (configuration or {}).get("backup", {}).get("retention", {})
    images = settings.get("images", {})
    policy = str(settings.get("policy", "keep_newest"))
    high = float(settings.get("high_watermark_percent", 90))
    low = float(settings.get("low_watermark_percent", 80))
    minimum_free = int(settings.get("minimum_free_bytes", 104857600))
    priorities = (settings.get("priorities", {}) or {})
    feed = int(images.get("feed_priority", priorities.get("feed", 80)))
    full = int(images.get("full_resolution_priority", priorities.get("full_resolution", 40)))
    if policy not in {"keep_oldest", "keep_newest", "keep_highest_priority", "prune"}:
        raise ValueError("backup.retention.policy must be keep_oldest, keep_newest, keep_highest_priority, or prune")
    if not 0 <= low < high <= 100:
        raise ValueError("backup retention watermarks must satisfy 0 <= low < high <= 100")
    if minimum_free < 0 or not all(0 <= value <= 99 for value in (feed, full)):
        raise ValueError("backup retention priorities and minimum_free_bytes are invalid")
    prune_every = int(settings.get("prune_every", 2))
    if policy == "prune" and prune_every < 2:
        raise ValueError("backup.retention.prune_every must be at least 2")
    return RetentionConfig(policy, high, low, minimum_free, feed, full, prune_every)


class BackupRetention:
    def __init__(self, root: Path, config: RetentionConfig) -> None:
        self.root = root.resolve()
        self.config = config
        self.lock = threading.RLock()
        self.backup_enabled = True

    def _usage(self) -> tuple[int, int, int]:
        usage = shutil.disk_usage(self.root)
        return usage.total, usage.used, usage.free

    def _under_pressure(self) -> bool:
        total, used, free = self._usage()
        return used / total * 100 >= self.config.high_watermark_percent or free < self.config.minimum_free_bytes

    def _target_reached(self) -> bool:
        total, used, free = self._usage()
        return used / total * 100 <= self.config.low_watermark_percent and free >= self.config.minimum_free_bytes

    def _artifacts(self) -> list[Artifact]:
        result: list[Artifact] = []
        for path in self.root.glob("readings-*-p*.csv"):
            try:
                priority = int(path.stem.rsplit("-p", 1)[1])
                result.append(Artifact(path, path.stat().st_mtime, priority))
            except (ValueError, OSError):
                continue
        images = self.root / "images"
        if images.exists():
            for path in (*images.glob("image-*.jpg"), *images.glob("feed-*.jpg")):
                metadata = path.with_suffix(".json")
                priority = 99
                created = path.stat().st_mtime
                try:
                    data = json.loads(metadata.read_text(encoding="utf-8"))
                    priority = int(data.get("priority", priority))
                    created = datetime.fromisoformat(data["timestamp"]).timestamp()
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    pass
                result.append(Artifact(path, created, priority, (metadata,)))
        return result

    def _prune_readings(self, protected: set[Path]) -> None:
        """Remove every Nth reading per sensor from managed CSV files."""
        every = getattr(self.config, "prune_every", 0)
        if every < 2:
            return
        counts: dict[str, int] = {}
        files = sorted(self.root.glob("readings-*-p*.csv"), key=lambda path: path.stat().st_mtime)
        for path in files:
            if path.resolve() in protected:
                continue
            try:
                with path.open("r", newline="", encoding="utf-8") as source:
                    rows = list(csv.DictReader(source))
                if not rows:
                    continue
                kept: list[dict[str, str]] = []
                fieldnames = list(rows[0].keys())
                for row in rows:
                    sensor = row.get("sensor_name", "")
                    counts[sensor] = counts.get(sensor, 0) + 1
                    if counts[sensor] % every != 0:
                        kept.append(row)
                if len(kept) != len(rows):
                    temporary = path.with_suffix(path.suffix + ".tmp")
                    with temporary.open("w", newline="", encoding="utf-8") as target:
                        writer = csv.DictWriter(target, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(kept)
                    temporary.replace(path)
            except (OSError, csv.Error, IndexError):
                logger.warning("Could not prune backup readings in %s", path, exc_info=True)

    def cleanup(self, protected: set[Path] | None = None) -> bool:
        with self.lock:
            if not self._under_pressure():
                self.backup_enabled = True
                return True
            protected = {path.resolve() for path in (protected or set())}
            if self.config.policy == "prune":
                self._prune_readings(protected)
                if self._target_reached():
                    self.backup_enabled = True
                    return True
            artifacts = [item for item in self._artifacts() if item.path.resolve() not in protected]
            if self.config.policy == "keep_highest_priority":
                artifacts.sort(key=lambda item: (item.priority, item.created_at), reverse=True)
            elif self.config.policy == "keep_oldest":
                artifacts.sort(key=lambda item: item.created_at, reverse=True)
            else:
                artifacts.sort(key=lambda item: item.created_at)
            for artifact in artifacts:
                if self._target_reached():
                    self.backup_enabled = True
                    return True
                for path in (artifact.path, *artifact.companions):
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
                    except OSError:
                        logger.warning("Could not remove backup artifact %s", path, exc_info=True)
            self.backup_enabled = self._target_reached()
            return self.backup_enabled


_MANAGERS: dict[Path, BackupRetention] = {}
_MANAGERS_LOCK = threading.Lock()


def get_retention(root: Path, configuration: dict[str, Any] | None = None) -> BackupRetention:
    key = root.resolve()
    with _MANAGERS_LOCK:
        manager = _MANAGERS.get(key)
        if manager is None:
            manager = BackupRetention(key, load_retention_config(configuration))
            _MANAGERS[key] = manager
        return manager
