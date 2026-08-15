from pathlib import Path
import tomllib

_path = Path(__file__).resolve().parents[3] / "config" / "topics.toml"
with _path.open("rb") as _file:
    TOPICS: dict[str, str] = tomllib.load(_file).get("topics", {})


def topic(name: str) -> str:
    return TOPICS[name]
