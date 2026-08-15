from __future__ import annotations

from dataclasses import dataclass

from muninn_prototype.modules.adapters.sensor_adapter import SensorAdapter


@dataclass(frozen=True, slots=True)
class SensorConfig:
    name: str
    sensor: str
    i2c_address: int
    adapter: SensorAdapter
    poll_hz: float = 1.0
    priority: int = 99
