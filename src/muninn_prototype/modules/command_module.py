from __future__ import annotations

from typing import Any

from pubsub import pub

from .base_module import BaseModule
from .message_ingress_module import InboundMessage
from .command_events import COMMAND_TOPIC, load_commands
from .topic_config import topic


def verify_command(command: str, commands: dict[str, str]) -> bool:
    """Return whether *command* is a command supported by this module."""
    parts = command.strip().split()
    if not parts:
        return False
    if command.strip() in commands:
        return True
    return (
        len(parts) == 2
        and parts[0] in commands
        and parts[0] == "set_fan_speed"
        and parts[1].isdigit()
        and 0 <= int(parts[1]) <= 100
    )


class CommandModule(BaseModule):
    """Dispatch inbound commands to the modules that implement them."""

    def __init__(self) -> None:
        super().__init__()
        self._subscribed = False
        self._commands: dict[str, str] = {}

    def _on_message(self, message: InboundMessage) -> None:
        if message.topic.rsplit("/", 1)[-1] != "commands":
            return

        command = message.payload.strip()
        if not verify_command(command, self._commands):
            return

        command_name = command.split(maxsplit=1)[0]
        event = self._commands.get(command, self._commands.get(command_name))
        if event is None:
            return
        if command_name == "set_fan_speed":
            event = f"{event} {command.split(maxsplit=1)[1]}"
        pub.sendMessage(COMMAND_TOPIC, command=event)

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        self._commands = load_commands()
        if not self._subscribed:
            pub.subscribe(self._on_message, topic("inbound_messages"))
            self._subscribed = True
        super().initiate()

    def shutdown(self) -> None:
        if self._subscribed:
            pub.unsubscribe(self._on_message, topic("inbound_messages"))
            self._subscribed = False
        super().shutdown()


def initiate() -> None:
    """Backward-compatible command-module entry point."""
    pub.sendMessage(topic("status"), message="ok")
