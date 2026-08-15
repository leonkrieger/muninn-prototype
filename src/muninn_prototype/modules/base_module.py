from pubsub import pub
from .topic_config import topic
import threading
import time
import logging

logger = logging.getLogger(__name__)

class BaseModule:
    def __init__(self, heartbeat_interval_s: float = 5.0):
        self._heartbeat_thread = None
        self._heartbeat_interval_s = heartbeat_interval_s

    def configure_heartbeat_interval(self, heartbeat_interval_s: float):
        self._heartbeat_interval_s = heartbeat_interval_s

    def heartbeat(self):
        while True:
            pub.sendMessage(topic("heartbeats"), module=self.__class__.__name__)
            time.sleep(self._heartbeat_interval_s)

    def initiate(self):
        logger.info("Initiating %s", self.__class__.__name__)
        
        self._heartbeat_thread = threading.Thread(
            target=self.heartbeat,
            daemon=True
        )
        self._heartbeat_thread.start()

        logger.info("%s initiated", self.__class__.__name__)
