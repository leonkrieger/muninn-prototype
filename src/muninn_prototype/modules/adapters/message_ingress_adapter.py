from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class MessageIngressAdapter(ABC):
    """Transport-neutral source of inbound messages."""

    @abstractmethod
    def receive_loop(self, on_message: Callable[[str, str], None], stop_event) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
