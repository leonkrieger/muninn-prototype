from __future__ import annotations

from typing import Any

from .display_adapter import DisplayAdapter
from .qwiic_alphanumeric_display_adapter import QwiicAlphanumericDisplayAdapter


def create_display_adapter(name: str = "qwiic_alphanumeric") -> DisplayAdapter:
    if name in {"qwiic", "qwiic_alphanumeric"}:
        return QwiicAlphanumericDisplayAdapter()
    raise ValueError(f"Unknown display adapter: {name}")


def display_adapter_from_configuration(
    configuration: dict[str, Any] | None,
) -> DisplayAdapter:
    configuration = configuration or {}
    return create_display_adapter(
        str(configuration.get("adapter", "qwiic_alphanumeric"))
    )
