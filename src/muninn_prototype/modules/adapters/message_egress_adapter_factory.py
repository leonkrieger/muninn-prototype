from __future__ import annotations

import logging
from typing import Any

from .message_egress_adapter import MessageEgressAdapter
from .zeromq_egress_adapter import ZeroMQEgressAdapter

logger = logging.getLogger(__name__)


def build_message_egress_adapter(
    configuration: dict[str, Any] | None = None,
) -> MessageEgressAdapter | None:
    configuration = configuration or {}
    settings = configuration.get("egress", configuration.get("publisher", {}))
    name = (
        str(settings.get("transport", settings.get("pub_backend", "zeromq")))
        .strip()
        .lower()
    )
    if name in {"", "zeromq", "zmq"}:
        return ZeroMQEgressAdapter()
    logger.warning(
        "Skipping message egress because no adapter matches transport %s", name
    )
    return None
