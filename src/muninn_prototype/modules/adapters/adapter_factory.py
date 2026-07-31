from __future__ import annotations

import logging

from muninn_prototype.modules.adapters.sensor_adapter import SensorAdapter
from muninn_prototype.modules.adapters.bme680_sensor_adapter import BME680SensorAdapter
from muninn_prototype.modules.adapters.emc2101_sensor_adapter import EMC2101SensorAdapter
from muninn_prototype.modules.adapters.ina219_sensor_adapter import INA219SensorAdapter


logger = logging.getLogger(__name__)


def build_sensor_adapter(sensor_name: str) -> SensorAdapter | None:
    normalized_name = sensor_name.strip().lower()

    if normalized_name == "bme680":
        if not BME680SensorAdapter.is_available():
            logger.warning(
                "Skipping sensor %s because the BME680 adapter is not available",
                sensor_name,
            )
            return None

        return BME680SensorAdapter()

    if normalized_name == "emc2101":
        if not EMC2101SensorAdapter.is_available():
            logger.warning(
                "Skipping sensor %s because the EMC2101 adapter is not available",
                sensor_name,
            )
            return None

        return EMC2101SensorAdapter()

    if normalized_name == "ina219":
        if not INA219SensorAdapter.is_available():
            logger.warning(
                "Skipping sensor %s because the INA219 adapter is not available",
                sensor_name,
            )
            return None

        return INA219SensorAdapter()

    logger.warning("Skipping sensor %s because no adapter matches that name", sensor_name)
    return None
