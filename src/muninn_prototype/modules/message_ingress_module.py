from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from pubsub import pub

from .adapters.message_ingress_adapter import MessageIngressAdapter
from .adapters.message_ingress_adapter_factory import build_message_ingress_adapter
from .base_module import BaseModule
from .topic_config import topic

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InboundMessage:
    topic: str
    payload: str


class MessageIngressModule(BaseModule):
    def __init__(self, adapter: MessageIngressAdapter | None = None) -> None:
        super().__init__()
        self._adapter = adapter
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _on_message(self, topic: str, payload: str) -> None:
        pub.sendMessage(topic("inbound_messages"), message=InboundMessage(topic, payload))

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        settings = (configuration or {}).get("ingress", {})
        if not bool(settings.get("enabled", False)):
            logger.info("Message ingress is disabled")
            return
        self._adapter = self._adapter or build_message_ingress_adapter(configuration)
        if self._adapter is None:
            pub.sendMessage(topic("errors"), message="No message ingress adapter available", error_code="ingress_unavailable")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._adapter.receive_loop, args=(self._on_message, self._stop_event), daemon=True, name="MessageIngressModule")
        self._thread.start()
        super().initiate()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._adapter is not None:
            self._adapter.close()
