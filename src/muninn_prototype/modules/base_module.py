from pubsub import pub
import threading
import time


class BaseModule:
    def __init__(self):
        self._heartbeat_thread = None

    def heartbeat(self):
        while True:
            pub.sendMessage("heartbeat", module=self.__class__.__name__)
            time.sleep(5)

    def initiate(self):
        pub.sendMessage("status", message="ok")

        self._heartbeat_thread = threading.Thread(
            target=self.heartbeat,
            daemon=True
        )
        self._heartbeat_thread.start()