import logging
import inspect
import time
from pubsub import pub
from muninn_prototype.modules import MODULES
from muninn_prototype.modules.base_module import BaseModule

logger = logging.getLogger(__name__)

def on_heartbeat(module):
    logger.info(f"Received heartbeat from: {module}")


def _initiate_module(module, configuration: dict | None = None):
    initiate = getattr(module, "initiate", None)
    if initiate is None:
        return

    if len(inspect.signature(initiate).parameters) == 0:
        initiate()
        return

    initiate(configuration)

def initiate_suit(configuration: dict | None = None):
    logger.info("Initiating suit ...")

    heartbeat_interval_s = float((configuration or {}).get("heartbeat", {}).get("hb_freq_s", 10.0))

    for module in MODULES:
        if isinstance(module, BaseModule):
            module.configure_heartbeat_interval(heartbeat_interval_s)

        _initiate_module(module, configuration)
        time.sleep(1)

    pub.subscribe(on_heartbeat, "heartbeat")

    logger.info("Suit initiated")