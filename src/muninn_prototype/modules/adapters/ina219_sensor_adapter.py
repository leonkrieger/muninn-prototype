from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from muninn_prototype.modules.adapters.sensor_adapter import SensorAdapter
from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading


class INA219SensorAdapter(SensorAdapter):
    """Read battery capacity from the Waveshare INA219 driver.

    Copyright (c) Waveshare. The INA219 driver used by this adapter is
    provided by Waveshare, the manufacturer of the INA219 board.
    """

    _sensor_cache: dict[int, Any] = {}
    _sensor_cache_lock = threading.Lock()

    @classmethod
    def is_available(cls) -> bool:
        try:
            import smbus  # noqa: F401
            from tools.INA219 import INA219  # noqa: F401
        except ImportError:
            return False

        return True

    def _get_sensor(self, i2c_address: int):
        with self._sensor_cache_lock:
            cached_sensor = self._sensor_cache.get(i2c_address)
            if cached_sensor is not None:
                return cached_sensor

        from tools.INA219 import INA219

        sensor = INA219(addr=i2c_address)

        with self._sensor_cache_lock:
            self._sensor_cache[i2c_address] = sensor

        return sensor

    def read(self, i2c_address: int) -> list[SensorReading]:
        sensor = self._get_sensor(i2c_address)
        bus_voltage = sensor.getBusVoltage_V()

        # Match the capacity estimate in the Waveshare INA219 example:
        # 6.0 V is empty and 8.4 V is full for the monitored battery.
        capacity = max(0.0, min(100.0, (bus_voltage - 6.0) / 2.4 * 100.0))

        return [
            SensorReading(
                timestamp=datetime.now(timezone.utc),
                measurement="capacity",
                unit="percent",
                value=capacity,
            )
        ]
