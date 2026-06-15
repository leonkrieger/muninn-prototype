from pathlib import Path

def get_project_root(start_path: Path) -> Path:
    """Find project root containing pyproject.toml by walking up parents."""
    for parent in start_path.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("No pyproject.toml found in any parent directory!")