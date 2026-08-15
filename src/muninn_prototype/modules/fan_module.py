from __future__ import annotations

import logging
from typing import Any

from pubsub import pub
from .topic_config import topic

from muninn_prototype.modules.base_module import BaseModule

logger = logging.getLogger(__name__)


class FanModule(BaseModule):
    """Run EMC2101 fan output continuously at full speed."""
    # TODO: implement fan control

    def __init__(self) -> None:
        super().__init__()
        self._controller: Any = None

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        super().initiate()
        config = (configuration or {}).get("fan", {})
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
            self._controller.manual_fan_speed = 100
            logger.info("Started EMC2101 fan at 100%% (address 0x%02X)", address)
        except Exception as error:
            logger.error("Fan unavailable: %s", error)
            pub.sendMessage(topic("errors"), message="", error_code="fan_unavailable")

    def shutdown(self) -> None:
        if self._controller is not None:
            try:
                self._controller.manual_fan_speed = 0
                logger.info("Stopped EMC2101 fan")
            except Exception:
                logger.exception("Failed to stop EMC2101 fan during shutdown")
        self._controller = None
