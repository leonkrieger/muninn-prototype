import logging 
import tomllib
import signal
import time

from pathlib import Path
from datetime import datetime
from muninn_prototype.utils.get_project_root import get_project_root
from muninn_prototype.config_validation import validate_configuration

root = get_project_root(Path(__file__).resolve())
with open(root / "config" / "defaults.toml", "rb") as defaults_file:
    configuration = tomllib.load(defaults_file)
validate_configuration(configuration)

# Importing the module registry constructs the runtime module objects. Keep it
# after configuration validation so invalid defaults cannot initialize hardware
# or other runtime resources.
from muninn_prototype.modules import master_module

logs_dir = root / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = logs_dir / f"run_{timestamp}.log"

log_level_name = str(configuration.get("logging", {}).get("level", "INFO")).upper()
log_level = getattr(logging, log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='[ %(asctime)s ] [%(module)s] [%(levelname)s] [%(message)s]',
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
    shutting_down = False

    def handle_sigint(_signum, _frame):
        nonlocal shutting_down
        shutting_down = True
        logger.info("Received Ctrl+C. Shutting down.")

    signal.signal(signal.SIGINT, handle_sigint)
    try:
        master_module.initiate_suit(configuration)
        while not shutting_down:
            time.sleep(1)
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler)
        master_module.shutdown_suit()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    main()
    
