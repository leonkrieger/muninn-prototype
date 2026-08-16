from __future__ import annotations

import logging
from typing import Any

from .message_ingress_adapter import MessageIngressAdapter
from .zeromq_ingress_adapter import ZeroMQIngressAdapter

logger = logging.getLogger(__name__)


def build_message_ingress_adapter(
    configuration: dict[str, Any] | None = None,
) -> MessageIngressAdapter | None:
    settings = (configuration or {}).get("ingress", {})
    name = str(settings.get("transport", "zeromq")).strip().lower()
    if name in {"zeromq", "zmq"}:
        adapter = ZeroMQIngressAdapter()
        adapter.configure(
            str(settings.get("endpoint", "tcp://127.0.0.1:5556")),
            str(settings.get("topic", "")),
        )
        return adapter
    logger.warning(
        "Skipping message ingress because no adapter matches transport %s", name
    )
    return None
