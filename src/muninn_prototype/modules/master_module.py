import logging
from pubsub import pub
from muninn_prototype.modules import MODULES

logger = logging.getLogger(__name__)

def on_status(message):
    logger.debug(f"Received status: {message}")

def on_heartbeat(module):
    logger.info(f"Received heartbeat from: {module}")

def initiate_suit():
    logger.info("Initiating suit ...")

    pub.subscribe(on_status, "status")

    for module in MODULES:
        module.initiate()

    pub.subscribe(on_heartbeat, "heartbeat")

    logger.info("Suit initiated")