from __future__ import annotations

import logging
from typing import Any

from pubsub import pub
from .topic_config import topic

from muninn_prototype.modules.base_module import BaseModule

logger = logging.getLogger(__name__)


class FanModule(BaseModule):
    """Control the EMC2101 fan and respond to thermal warnings."""

    def __init__(self) -> None:
        super().__init__()
        self._controller: Any = None
        self._subscribed = False
        self._normal_speed = 50

    def _on_command(self, command: str) -> None:
        parts = command.split()
        if len(parts) != 2 or parts[0] != "set_fan_speed" or self._controller is None:
            return

        try:
            speed = int(parts[1])
            if not 0 <= speed <= 100:
                return
            self._controller.manual_fan_speed = speed
            logger.info("Set EMC2101 fan speed to %d%%", speed)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid fan-speed command: %s", command)
        except Exception:
            logger.exception("Failed to set fan speed")

    def _on_warning(
        self,
        module: str,
        message: str,
        recovered: bool,
        measurement: str | None = None,
        **_: Any,
    ) -> None:
        if measurement != "temperature" or self._controller is None:
            return

        try:
            speed = self._normal_speed if recovered else 100
            self._controller.manual_fan_speed = speed
            logger.info("Temperature warning %s; set fan speed to %d%%", "recovered" if recovered else "received", speed)
        except Exception:
            logger.exception("Failed to increase fan speed after high temperature warning")

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        super().initiate()
        config = (configuration or {}).get("fan", {})
        self._normal_speed = max(0, min(100, int(config.get("normal_speed", 50))))
        if not config.get("enabled", True):
            logger.info("Fan disabled by configuration")
            return

        address = config.get("i2c_address", "0x4C")
        address = int(address, 0) if isinstance(address, str) else int(address)
        try:
            import board
            from adafruit_emc2101 import EMC2101

            # EMC2101 adress is fixed
            self._controller = EMC2101(board.I2C())
            self._controller.manual_fan_speed = self._normal_speed
            pub.subscribe(self._on_warning, "warning")
            pub.subscribe(self._on_command, topic("commands"))
            self._subscribed = True
            logger.info("Started EMC2101 fan at %d%% (address 0x%02X)", self._normal_speed, address)
        except Exception as error:
            logger.error("Fan unavailable: %s", error)
            pub.sendMessage(topic("errors"), message="", error_code="fan_unavailable")

    def shutdown(self) -> None:
        if self._subscribed:
            pub.unsubscribe(self._on_warning, "warning")
            self._subscribed = False
        pub.unsubscribe(self._on_command, topic("commands"))
        if self._controller is not None:
            try:
                self._controller.manual_fan_speed = 0
                logger.info("Stopped EMC2101 fan")
            except Exception:
                logger.exception("Failed to stop EMC2101 fan during shutdown")
        self._controller = None
        super().shutdown()
