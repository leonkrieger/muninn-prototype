from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from muninn_prototype.modules.adapters.sensor_adapter import SensorAdapter
from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading


class EMC2101SensorAdapter(SensorAdapter):
    _sensor_cache: dict[int, Any] = {}
    _external_temperature_available: dict[int, bool] = {}
    _sensor_cache_lock = threading.Lock()

    @classmethod
    def is_available(cls) -> bool:
        try:
            import board
            from adafruit_emc2101 import EMC2101
        except ImportError:
            return False

        return True

    def _get_sensor(self, i2c_address: int):
        with self._sensor_cache_lock:
            cached_sensor = self._sensor_cache.get(i2c_address)
            if cached_sensor is not None:
                return cached_sensor

        import board
        from adafruit_emc2101 import EMC2101

        sensor = EMC2101(board.I2C())

        with self._sensor_cache_lock:
            self._sensor_cache[i2c_address] = sensor

        return sensor

    def read(self, i2c_address: int) -> list[SensorReading]:
        sensor = self._get_sensor(i2c_address)

        timestamp = datetime.now(timezone.utc)
        readings = [
            SensorReading(timestamp=timestamp, measurement="temp internal", unit="Celsius", value=sensor.internal_temperature),
        ]

        with self._sensor_cache_lock:
            external_temperature_available = self._external_temperature_available.get(i2c_address, True)

        if external_temperature_available:
            try:
                external_temperature = sensor.external_temperature
            except RuntimeError as error:
                if "Open circuit" in str(error):
                    with self._sensor_cache_lock:
                        self._external_temperature_available[i2c_address] = False

                    return readings

                raise

            readings.append(
                SensorReading(timestamp=timestamp, measurement="temp external", unit="Celsius", value=external_temperature)
            )

        return readings