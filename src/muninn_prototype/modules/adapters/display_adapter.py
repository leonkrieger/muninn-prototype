"""Display adapter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DisplayAdapter(ABC):
    """

    ``error_codes`` contains the codes supported
    """

    error_codes: dict[str, str] = {}

    @abstractmethod
    def initiate(self) -> bool:
        """Initialize the hardware and return whether it is available."""

    @abstractmethod
    def write(self, value: str) -> None:
        """Write a rendered value to the display."""

    @abstractmethod
    def clear(self) -> None:
        """Clear the display."""

    def render(self, text: Any = "", status: Any | None = None,
               error_code: Any | None = None) -> str:
        identifier = str(error_code or status or "").strip()
        return str(self.error_codes.get(identifier, text)).strip()

