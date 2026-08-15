"""Internal command-event utilities shared by command producers and consumers."""

import tomllib
from pathlib import Path

from .topic_config import topic
from muninn_prototype.utils.get_project_root import get_project_root

COMMAND_TOPIC = topic("commands")


def load_commands() -> dict[str, str]:
    commands_path = get_project_root(Path(__file__).resolve()) / "config" / "commands.toml"
    try:
        with commands_path.open("rb") as commands_file:
            commands = tomllib.load(commands_file).get("commands", {})
    except (OSError, tomllib.TOMLDecodeError) as error:
        print(f"Unable to load command definitions from {commands_path}: {error}")
        return {}
    return {str(name).strip(): str(event).strip() for name, event in commands.items()}
