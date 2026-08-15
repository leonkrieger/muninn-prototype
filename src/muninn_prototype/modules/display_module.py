from __future__ import annotations

import logging
import threading
from typing import Any

from pubsub import pub

from muninn_prototype.modules.adapters.display_adapter import DisplayAdapter
from muninn_prototype.modules.adapters.display_adapter_factory import display_adapter_from_configuration
from muninn_prototype.modules.base_module import BaseModule
from muninn_prototype.modules.topic_config import topic

logger = logging.getLogger(__name__)
DISPLAY_TOPIC = topic("display")
STATUS_TOPIC = topic("errors")
DISPLAY_WIDTH = 4
BUTTON_GPIO = 16


class DisplayModule(BaseModule):
    """Publishes messages through display adapter."""

    def __init__(self, adapter: DisplayAdapter | None = None) -> None:
        super().__init__()
        self._adapter = adapter
        self._available = False
        self._write_lock = threading.Lock()
        self._subscribed = False
        self._clear_button: Any | None = None

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        if self._adapter is None:
            display_configuration = (configuration or {}).get("display", configuration)
            self._adapter = display_adapter_from_configuration(display_configuration)
        try:
            self._available = self._adapter.initiate()
            logger.info("Display adapter %s available=%r", type(self._adapter).__name__, self._available)
        except (ImportError, OSError, AttributeError, RuntimeError, ValueError):
            self._available = False
            logger.exception("Display adapter is unavailable")
        if not self._subscribed:
            pub.subscribe(self._on_display_message, DISPLAY_TOPIC)
            pub.subscribe(self._on_status_message, STATUS_TOPIC)
            self._subscribed = True
        self._setup_clear_button()
        super().initiate()

    def _setup_clear_button(self) -> None:
        try:
            from gpiozero import Button
            self._clear_button = Button(BUTTON_GPIO, pull_up=True, bounce_time=0.1)
            self._clear_button.when_pressed = self._clear_display
        except (ImportError, OSError, RuntimeError) as error:
            logger.warning("Display clear button unavailable: %s", error)

    @staticmethod
    def _clear_display() -> None:
        pub.sendMessage(DISPLAY_TOPIC, text=" " * DISPLAY_WIDTH)

    def shutdown(self) -> None:
        if self._clear_button is not None:
            self._clear_button.close()
            self._clear_button = None

    def _on_status_message(self, message: Any = "", status: Any | None = None,
                           error_code: Any | None = None, **kwargs: Any) -> None:
        self._on_display_message(text=message, status=status, error_code=error_code, **kwargs)

    def _on_display_message(self, text: Any = "", status: Any | None = None,
                            error_code: Any | None = None, **_: Any) -> None:
        if not self._available or self._adapter is None:
            return
        value = self._adapter.render(text, status, error_code)
        try:
            with self._write_lock:
                self._adapter.write(value)
        except Exception:
            logger.exception("Failed to write %r to display adapter", value)
