from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any

from pubsub import pub

from muninn_prototype.modules.adapters.publisher_adapter import PublisherAdapter
from muninn_prototype.modules.adapters.publisher_adapter_factory import build_publisher_adapter
from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading
from muninn_prototype.modules.base_module import BaseModule


logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "tcp://*:5555"
_DEFAULT_SUIT_ID = "delta-default"
_READINGS_TOPIC = "readings"

def _configured_suit_id(configuration: dict[str, Any] | None) -> str:
    candidate = (configuration or {}).get("suit", {}).get("suitID")
    suit_id = str(candidate).strip() if candidate is not None else ""

    if suit_id:
        logger.debug("Using publisher suit ID %s", suit_id)
        return suit_id

    logger.debug("No valid publisher suit ID configured; falling back to default: %s", _DEFAULT_SUIT_ID)
    return _DEFAULT_SUIT_ID


def _configured_endpoint(configuration: dict[str, Any] | None) -> str:
    candidate = (configuration or {}).get("publisher", {}).get("endpoint")
    endpoint = str(candidate).strip() if candidate is not None else ""

    if endpoint:
        logger.debug("Using publisher endpoint %s", endpoint)
        return endpoint

    logger.debug("No valid publisher endpoint configured; falling back to default: %s", _DEFAULT_ENDPOINT)
    return _DEFAULT_ENDPOINT


def _reading_to_payload(reading: SensorReading) -> dict[str, Any]:
    timestamp = reading.timestamp
    if isinstance(timestamp, datetime):
        timestamp_value = timestamp.isoformat()
    else:
        timestamp_value = str(timestamp)

    return {
        "reading_id": reading.reading_id,
        "timestamp": timestamp_value,
        "sensor_name": reading.sensor_name,
        "sensor_type": reading.sensor_type,
        "measurement": reading.measurement,
        "unit": reading.unit,
        "value": reading.value,
    }


class PublisherModule(BaseModule):
    def __init__(self):
        super().__init__()
        self._subscribed = False
        self._endpoint = _DEFAULT_ENDPOINT
        self._suit_id = _DEFAULT_SUIT_ID
        self._publish_queue: queue.Queue[SensorReading | None] = queue.Queue(maxsize=1000)
        self._publisher_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._publisher_adapter: PublisherAdapter | None = None

    def _publish_loop(self) -> None:
        adapter = self._publisher_adapter
        if adapter is None:
            logger.error("Failed to start publisher because no adapter is configured")
            return
        try:
            adapter.connect(self._endpoint)
            topic = f"{self._suit_id}/{_READINGS_TOPIC}"
            while not self._stop_event.is_set():
                reading = self._publish_queue.get()
                if reading is None:
                    break
                adapter.publish(topic, json.dumps(_reading_to_payload(reading), separators=(",", ":"), default=str))
                logger.debug("Published reading %s", reading.reading_id)
        except Exception:
            logger.exception("Publisher transport of reading failed")
        finally:
            adapter.close()

    def _on_reading(self, reading: SensorReading) -> None:
        try:
            self._publish_queue.put_nowait(reading)
        except queue.Full:
            logger.warning("Dropping reading %s because the publisher queue is full", reading.reading_id)

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        self._suit_id = _configured_suit_id(configuration)
        self._endpoint = _configured_endpoint(configuration)
        self._publisher_adapter = build_publisher_adapter(configuration)

        if self._publisher_adapter is None:
            logger.warning("Publisher will not publish because no publisher adapter is available")
            return
        if not self._subscribed:
            pub.subscribe(self._on_reading, "readings")
            self._subscribed = True
        if self._publisher_thread is None or not self._publisher_thread.is_alive():
            self._stop_event.clear()
            self._publisher_thread = threading.Thread(target=self._publish_loop, daemon=True, name="PublisherModule:ZeroMQ")
            self._publisher_thread.start()
        super().initiate()
        logger.info("Started publisher module for suit %s", self._suit_id)

    def shutdown(self) -> None:
        self._stop_event.set()
        try:
            self._publish_queue.put_nowait(None)
        except queue.Full:
            logger.debug("Publisher queue was full while shutting down")
