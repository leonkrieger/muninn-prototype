from __future__ import annotations

from abc import ABC, abstractmethod


class PublisherAdapter(ABC):
    @abstractmethod
    def connect(self, endpoint: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def publish(self, topic: str, payload: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError