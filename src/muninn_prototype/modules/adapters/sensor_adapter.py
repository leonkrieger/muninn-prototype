from __future__ import annotations

from abc import ABC, abstractmethod

from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading


class SensorAdapter(ABC):
    @abstractmethod
    def read(self, i2c_address: int) -> list[SensorReading]:
        raise NotImplementedError