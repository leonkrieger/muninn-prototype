from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading
from muninn_prototype.modules.adapters.sensor_adapter import SensorAdapter


class BME680SensorAdapter(SensorAdapter):
    def __init__(self, sea_level_pressure_hpa: float | None = None):
        self._sea_level_pressure_hpa = sea_level_pressure_hpa

    _sensor_cache: dict[int, Any] = {}
    _sensor_cache_lock = threading.Lock()

    @classmethod
    def is_available(cls) -> bool:
        try:
            import board
            from adafruit_bme680 import Adafruit_BME680_I2C
        except ImportError:
            return False

        return True

    def _get_sensor(self, i2c_address: int):
        with self._sensor_cache_lock:
            cached_sensor = self._sensor_cache.get(i2c_address)
            if cached_sensor is not None:
                return cached_sensor

        import board
        from adafruit_bme680 import Adafruit_BME680_I2C

        sensor = Adafruit_BME680_I2C(board.I2C(), address=i2c_address)

        if self._sea_level_pressure_hpa is not None:
            sensor.sea_level_pressure = self._sea_level_pressure_hpa

        with self._sensor_cache_lock:
            self._sensor_cache[i2c_address] = sensor

        return sensor

    def read(self, i2c_address: int) -> list[SensorReading]:
        sensor = self._get_sensor(i2c_address)

        timestamp = datetime.now(timezone.utc)
        return [
            SensorReading(
                timestamp=timestamp,
                measurement="temperature",
                unit="Celsius",
                value=sensor.temperature,
            ),
            SensorReading(
                timestamp=timestamp,
                measurement="humidity",
                unit="percent",
                value=sensor.humidity,
            ),
            SensorReading(
                timestamp=timestamp,
                measurement="pressure",
                unit="hPa",
                value=sensor.pressure,
            ),
            SensorReading(
                timestamp=timestamp, measurement="gas", unit="ohm", value=sensor.gas
            ),
            SensorReading(
                timestamp=timestamp,
                measurement="altitude",
                unit="m",
                value=sensor.altitude,
            ),
        ]
