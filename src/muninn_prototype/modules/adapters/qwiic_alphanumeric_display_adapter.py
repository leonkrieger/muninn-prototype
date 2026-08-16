from __future__ import annotations

from typing import Any

from .display_adapter import DisplayAdapter


class QwiicAlphanumericDisplayAdapter(DisplayAdapter):
    """Adapter for SparkFun four-character Qwiic alphanumeric display."""

    error_codes = {
        "display_unavailable": "DERR",
        "sensor_unavailable": "SERR",
        "publisher_unavailable": "PERR",
    }
    width = 4

    def __init__(self) -> None:
        self._display: Any | None = None

    def initiate(self) -> bool:
        import qwiic_alphanumeric

        self._display = qwiic_alphanumeric.QwiicAlphanumeric()
        return self._display.begin() is not False

    def write(self, value: str) -> None:
        if self._display is not None:
            self._display.print(value[: self.width])

    def clear(self) -> None:
        self.write(" " * self.width)
