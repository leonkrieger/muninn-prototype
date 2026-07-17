from __future__ import annotations

import logging
import threading
from typing import Any

from pubsub import pub

from muninn_prototype.modules.base_module import BaseModule

logger = logging.getLogger(__name__)

DISPLAY_TOPIC = "display"
STATUS_TOPIC = "error"
DISPLAY_WIDTH = 4

ERROR_CODE_REGISTRY: dict[str, str] = {
    "display_unavailable": "DERR",
    "sensor_unavailable": "SERR",
    "publisher_unavailable": "PERR",
}

class DisplayModule(BaseModule):
    """Publishes application messages to the SparkFun Qwiic ALPHANUMERIC Display."""

    def __init__(self) -> None:
        super().__init__()
        self._display: Any | None = None
        self._available = False
        self._write_lock = threading.Lock()
        self._subscribed = False

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        del configuration  # Reserved for possible future display configuration.

        try:
            import qwiic_alphanumeric

            display = qwiic_alphanumeric.QwiicAlphanumeric()
            self._display = display
            # Some released qwiic_alphanumeric versions perform successful
            # initialization but omit the documented True return value.
            # Treat only an explicit False as a failed device detection.
            begin_result = display.begin()
            self._available = begin_result is not False
            if self._available:
                logger.info("Qwiic alphanumeric display detected (begin=%r)", begin_result)
            else:
                logger.error("Qwiic alphanumeric display is not available")
        except AttributeError as error:
            # qwiic_i2c cannot provide an I2C backend on unsupported hosts
            # (e.g. Windows), and the library currently fails later
            # with an AttributeError when _i2c is None.
            self._display = None
            self._available = False
            logger.warning(
                "Qwiic alphanumeric display skipped: I2C is unsupported on this platform (%s)",
                error,
            )
        except (ImportError, OSError) as error:
            self._display = None
            self._available = False
            logger.warning(
                "Qwiic alphanumeric display skipped: I2C is unavailable (%s)",
                error,
            )
        except Exception:
            self._display = None
            self._available = False
            logger.exception("Failed to initialize Qwiic alphanumeric display")

        if not self._subscribed:
            pub.subscribe(self._on_display_message, DISPLAY_TOPIC)
            pub.subscribe(self._on_status_message, STATUS_TOPIC)
            self._subscribed = True

        # The module remains alive in degraded mode when no hardware exists.
        super().initiate()

    def _on_status_message(
        self,
        message: Any = "",
        status: Any | None = None,
        error_code: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self._on_display_message(
            text=message,
            status=status,
            error_code=error_code,
            **kwargs,
        )

    def _on_display_message(
        self,
        text: Any = "",
        status: Any | None = None,
        error_code: Any | None = None,
        **_: Any,
    ) -> None:
        value = self._display_value(text, status, error_code)
        if not self._available or self._display is None:
            return

        # Handle empty/whitespace message as clear-display command.
        value = value or (" " * DISPLAY_WIDTH)

        try:
            with self._write_lock:
                if len(value) > DISPLAY_WIDTH:
                    # The SparkFun package provides shifting, not a scroll()
                    # method. Printing the leading four characters keeps the
                    # write path compatible with all supported releases.
                    self._display.print(value[:DISPLAY_WIDTH])
                else:
                    self._display.print(value)
        except Exception:
            logger.exception("Failed to write %r to the display", value)

    @staticmethod
    def _display_value(text: Any, status: Any | None, error_code: Any | None) -> str:
        identifier = str(error_code or status or "").strip()
        mapped = ERROR_CODE_REGISTRY.get(identifier)
        return str(mapped if mapped is not None else text).strip()
