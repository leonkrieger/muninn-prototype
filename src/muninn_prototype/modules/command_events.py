"""Internal command-event utilities shared by command producers and consumers."""

import logging
import tomllib
from pathlib import Path

COMMAND_TOPIC = "module_commands"
logger = logging.getLogger(__name__)


def load_commands() -> dict[str, str]:
    commands_path = Path(__file__).resolve().parents[3] / "config" / "commands.toml"
    try:
        with commands_path.open("rb") as commands_file:
            commands = tomllib.load(commands_file).get("commands", {})
    except (OSError, tomllib.TOMLDecodeError) as error:
        logger.error("Unable to load command definitions from %s: %s", commands_path, error)
        return {}
    return {str(name).strip(): str(event).strip() for name, event in commands.items()}
