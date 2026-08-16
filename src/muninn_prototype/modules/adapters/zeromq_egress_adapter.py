from __future__ import annotations

import logging

import zmq

from .message_egress_adapter import MessageEgressAdapter

logger = logging.getLogger(__name__)


class ZeroMQEgressAdapter(MessageEgressAdapter):
    def __init__(self) -> None:
        self._context = zmq.Context.instance()
        self._socket: zmq.Socket | None = None
        self._endpoint = ""

    def connect(self, endpoint: str) -> None:
        self._endpoint = endpoint
        socket = self._context.socket(zmq.PUB)
        socket.linger = 0
        socket.sndhwm = 1000
        socket.sndtimeo = 1000
        socket.bind(endpoint)
        self._socket = socket

    def publish(self, topic: str, payload: str) -> None:
        if self._socket is None:
            raise RuntimeError("ZeroMQ egress is not connected")
        self._socket.send_multipart([topic.encode("utf-8"), payload.encode("utf-8")])

    def publish_multipart(self, topic: str, metadata: str, payload: bytes) -> None:
        if self._socket is None:
            raise RuntimeError("ZeroMQ egress is not connected")
        self._socket.send_multipart([topic.encode(), metadata.encode(), payload])

    def close(self) -> None:
        if self._socket is None:
            return
        try:
            self._socket.close()
        except Exception:
            logger.exception("Failed to close ZeroMQ egress socket for %s", self._endpoint)
        finally:
            self._socket = None
