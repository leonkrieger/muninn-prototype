from __future__ import annotations

import logging
from typing import Any

from muninn_prototype.modules.adapters.publisher_adapter import PublisherAdapter
from muninn_prototype.modules.adapters.zeromq_publisher_adapter import ZeroMQPublisherAdapter


logger = logging.getLogger(__name__)


def build_publisher_adapter(configuration: dict[str, Any] | None = None) -> PublisherAdapter | None:
    publisher_configuration = (configuration or {}).get("publisher", {})
    transport_name = str(
        publisher_configuration.get("pub_backend", publisher_configuration.get("transport", "zeromq"))
    ).strip().lower()

    if transport_name in {"", "zeromq", "zmq"}:
        return ZeroMQPublisherAdapter()

    logger.warning("Skipping publisher because no adapter matches backend %s", transport_name)
    return None