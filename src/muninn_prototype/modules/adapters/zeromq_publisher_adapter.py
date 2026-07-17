from __future__ import annotations

import logging

import zmq

from muninn_prototype.modules.adapters.publisher_adapter import PublisherAdapter


logger = logging.getLogger(__name__)


class ZeroMQPublisherAdapter(PublisherAdapter):
    def __init__(self) -> None:
        self._context = zmq.Context.instance()
        self._socket: zmq.Socket | None = None
        self._endpoint = ""

    def connect(self, endpoint: str) -> None:
        self._endpoint = endpoint
        socket = self._context.socket(zmq.PUB)
        socket.linger = 0
        socket.bind(endpoint)
        self._socket = socket

    def publish(self, topic: str, payload: str) -> None:
        if self._socket is None:
            raise RuntimeError("ZeroMQ publisher is not connected")

        self._socket.send_multipart([
            topic.encode("utf-8"),
            payload.encode("utf-8"),
        ])

    def close(self) -> None:
        if self._socket is None:
            return

        try:
            self._socket.close()
        except Exception:
            logger.exception("Failed to close ZeroMQ publisher socket for %s", self._endpoint)
        finally:
            self._socket = None