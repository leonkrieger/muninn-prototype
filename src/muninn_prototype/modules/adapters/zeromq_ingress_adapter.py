from __future__ import annotations

from collections.abc import Callable
import logging

import zmq

from .message_ingress_adapter import MessageIngressAdapter

logger = logging.getLogger(__name__)


class ZeroMQIngressAdapter(MessageIngressAdapter):
    """Receive topic/payload messages from a ZeroMQ PUB socket."""

    def __init__(self) -> None:
        self._context = zmq.Context.instance()
        self._socket: zmq.Socket | None = None

    def receive_loop(self, on_message: Callable[[str, str], None], stop_event) -> None:
        socket = self._context.socket(zmq.SUB)
        socket.linger = 0
        socket.rcvtimeo = 250
        self._socket = socket
        try:
            socket.connect(self._endpoint)
            socket.setsockopt_string(zmq.SUBSCRIBE, self._topic)
            while not stop_event.is_set():
                try:
                    parts = socket.recv_multipart()
                except zmq.Again:
                    continue
                if len(parts) != 2:
                    logger.warning(
                        "Ignoring malformed ZeroMQ message with %s frames", len(parts)
                    )
                    continue
                on_message(parts[0].decode("utf-8"), parts[1].decode("utf-8"))
        finally:
            self.close()

    def configure(self, endpoint: str, topic: str) -> None:
        self._endpoint, self._topic = endpoint, topic

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
