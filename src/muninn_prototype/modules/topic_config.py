import tomllib
from pathlib import Path

from muninn_prototype.utils.get_project_root import get_project_root

_path = get_project_root(Path(__file__).resolve()) / "config" / "topics.toml"
with _path.open("rb") as _file:
    TOPICS: dict[str, str] = tomllib.load(_file).get("topics", {})


def topic(name: str) -> str:
    return TOPICS[name]
