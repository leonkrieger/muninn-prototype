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
        self._heartbeat_stop_event = threading.Event()

    def configure_heartbeat_interval(self, heartbeat_interval_s: float):
        self._heartbeat_interval_s = heartbeat_interval_s

    def heartbeat(self):
        while not self._heartbeat_stop_event.is_set():
            pub.sendMessage(topic("heartbeats"), module=self.__class__.__name__)
            self._heartbeat_stop_event.wait(self._heartbeat_interval_s)

    def initiate(self):
        logger.info("Initiating %s", self.__class__.__name__)
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            logger.debug("Heartbeat already running for %s", self.__class__.__name__)
            return
        self._heartbeat_stop_event.clear()
        self._heartbeat_thread = threading.Thread(target=self.heartbeat, daemon=True)
        self._heartbeat_thread.start()

        logger.info("%s initiated", self.__class__.__name__)

    def shutdown(self):
        """Stop the module heartbeat and wait for it to exit."""
        self._heartbeat_stop_event.set()
        thread = self._heartbeat_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self._heartbeat_interval_s + 1.0))
        if thread is None or not thread.is_alive():
            self._heartbeat_thread = None
