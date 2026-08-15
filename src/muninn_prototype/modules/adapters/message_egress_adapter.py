from __future__ import annotations

from abc import ABC, abstractmethod


class MessageEgressAdapter(ABC):
    """Transport-neutral destination for outbound messages."""

    @abstractmethod
    def connect(self, endpoint: str) -> None: ...

    @abstractmethod
    def publish(self, topic: str, payload: str) -> None: ...

    def publish_multipart(self, topic: str, metadata: str, payload: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None: ...
