from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from pubsub import pub

from muninn_prototype.modules import base_module
from muninn_prototype.modules.adapters.adapter_factory import build_sensor_adapter
from muninn_prototype.modules.dataclasses.sensor_config import SensorConfig
from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading


logger = logging.getLogger(__name__)


def _is_missing_i2c_device_error(error: Exception) -> bool:
    if isinstance(error, ValueError) and "No I2C device at address" in str(error):
        return True

    if isinstance(error, OSError) and error.errno in {5, 121}:
        return True

    return False


def _sensor_address(sensor_config: dict[str, Any]) -> int:
    address = sensor_config.get("i2c_address", "0x77")
    if isinstance(address, int):
        return address

    return int(str(address), 0)


def load_default_sensors(configuration: dict[str, Any] | None) -> list[SensorConfig]:
    sensors: list[SensorConfig] = []
    sensor_configs = (configuration or {}).get("sensors", [])

    for sensor_config in sensor_configs:
        sensor_name = str(sensor_config.get("name", "")).strip()
        if not sensor_name:
            logger.warning("Skipping sensor entry without a name in defaults.toml")
            continue

        sensor_type = str(sensor_config.get("sensor", "")).strip()
        if not sensor_type:
            logger.warning("Skipping sensor %s because no sensor type was provided", sensor_name)
            continue

        adapter = build_sensor_adapter(sensor_type)
        if adapter is None:
            continue

        poll_hz = float(sensor_config.get("poll_hz", 0.2))
        if poll_hz <= 0:
            logger.warning("Skipping sensor %s because poll_hz must be greater than zero", sensor_name)
            continue
        if poll_hz >= 10:
            logger.warning("Skipping sensor %s because poll_hz must be smaller than or equal 10", sensor_name)
            continue

        sensors.append(
            SensorConfig(
                name=sensor_name,
                sensor=sensor_type,
                i2c_address=_sensor_address(sensor_config),
                adapter=adapter,
                poll_hz=poll_hz,
            )
        )

    return sensors


class SensorModule(base_module.BaseModule):
    def __init__(self, sensors: list[SensorConfig] | None = None):
        super().__init__()
        self._configured_sensors = sensors is not None
        self._sensors = list(sensors or [])
        self._sensor_threads: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._reading_id_lock = threading.Lock()
        self._next_reading_id = 0

    def _allocate_reading_id(self) -> int:
        with self._reading_id_lock:
            self._next_reading_id += 1
            return self._next_reading_id

    def initiate(self, configuration: dict[str, Any] | None = None):
        super().initiate()
        
        if not self._configured_sensors:
            self._sensors = load_default_sensors(configuration)
            
        for sensor in self._sensors:
            sensor_thread = threading.Thread(
                target=self._poll_sensor,
                args=(sensor,),
                daemon=True,
                name=f"{self.__class__.__name__}:{sensor.name}",
            )
            self._sensor_threads.append(sensor_thread)
            sensor_thread.start()

        logger.info("Started %d sensor polling threads", len(self._sensor_threads))

    def shutdown(self):
        self._stop_event.set()

    def _poll_sensor(self, sensor: SensorConfig):
        logger.info(
            "Starting sensor polling for %s (%s) at address 0x%02X at %.2f Hz",
            sensor.name,
            sensor.sensor,
            sensor.i2c_address,
            sensor.poll_hz,
        )

        if sensor.poll_hz <= 0:
            logger.warning(
                "Skipping sensor %s because poll_hz must be greater than zero",
                sensor.name,
            )
            return
        
        if sensor.poll_hz >= 10:
            logger.warning(
                "Skipping sensor %s because poll_hz must be smaller than or equal 10",
                sensor.name,
            )
            return

        

        poll_interval = 1.0 / sensor.poll_hz

        while not self._stop_event.is_set():
            try:
                sensor_readings = sensor.adapter.read(sensor.i2c_address)
            except Exception as error:
                if _is_missing_i2c_device_error(error):
                    logger.error(
                        "Stopping sensor polling for %s at address 0x%02X because the device is unavailable: %s",
                        sensor.name,
                        sensor.i2c_address,
                        error,
                    )
                    return

                logger.error(
                    "Failed to read sensor %s at address 0x%02X",
                    sensor.name,
                    sensor.i2c_address,
                )
            else:
                for sensor_reading in sensor_readings:
                    reading = SensorReading(
                        timestamp=sensor_reading.timestamp,
                        reading_id=self._allocate_reading_id(),
                        sensor_name=sensor.name,
                        sensor_type=sensor.sensor,
                        measurement=sensor_reading.measurement,
                        unit=sensor_reading.unit,
                        value=sensor_reading.value,
                    )
                    logger.debug(
                        "Sensor reading from %s (%s) at %s: %s %s = %s",
                        reading.sensor_name,
                        reading.sensor_type,
                        reading.timestamp.isoformat(),
                        reading.measurement,
                        reading.unit,
                        reading.value,
                    )
                    pub.sendMessage("readings", reading=reading)

            if self._stop_event.wait(poll_interval):
                break