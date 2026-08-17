from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SensorReading:
    timestamp: datetime
    reading_id: int = 0
    suit_id: str = ""
    sensor_name: str = ""
    sensor_type: str = ""
    measurement: str = ""
    unit: str = ""
    value: Any = None
    priority: int = 99
