import logging 
import tomllib
import threading

from pathlib import Path
from datetime import datetime
from muninn_prototype.utils.get_project_root import get_project_root
from muninn_prototype.modules import master_module

root = get_project_root(Path(__file__).resolve())
logs_dir = root / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = logs_dir / f"run_{timestamp}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_filename)),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def print_welcome_message():
    try:
        with open(root/"logo.txt", "r", encoding="utf-8") as file:
            print(file.read())
            print("=" * 40)
            print("  Muninn  |  v0.0.1")
            print("=" * 40)
    except FileNotFoundError:
        logger.warning("Error: logo.txt not found.")

def main():
    print_welcome_message()
    master_module.initiate_suit()
    threading.Event().wait()

if __name__ == "__main__":
    main()
    