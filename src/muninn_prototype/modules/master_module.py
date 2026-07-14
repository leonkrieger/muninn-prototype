import logging
from pubsub import pub
from muninn_prototype.modules import MODULES
from muninn_prototype.modules.base_module import BaseModule
from muninn_prototype.modules.sensor_module import SensorModule, load_default_sensors

logger = logging.getLogger(__name__)

def on_status(message):
    logger.debug(f"Received status: {message}")

def on_heartbeat(module):
    logger.info(f"Received heartbeat from: {module}")

def initiate_suit(configuration: dict | None = None):
    logger.info("Initiating suit ...")

    pub.subscribe(on_status, "status")

    heartbeat_interval_s = float((configuration or {}).get("heartbeat", {}).get("hb_freq_s", 10.0))

    sensor_module = SensorModule(load_default_sensors(configuration))
    sensor_module.configure_heartbeat_interval(heartbeat_interval_s)
    sensor_module.initiate()

    for module in MODULES:
        if isinstance(module, BaseModule):
            module.configure_heartbeat_interval(heartbeat_interval_s)

        module.initiate()


    pub.subscribe(on_heartbeat, "heartbeat")

    logger.info("Suit initiated")