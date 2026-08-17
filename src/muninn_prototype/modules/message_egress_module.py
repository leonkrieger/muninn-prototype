from __future__ import annotations

import json
import logging
import queue
import threading
from datetime import datetime
from typing import Any

from pubsub import pub

from muninn_prototype.modules.adapters.message_egress_adapter import (
    MessageEgressAdapter,
)
from muninn_prototype.modules.adapters.message_egress_adapter_factory import (
    build_message_egress_adapter,
)
from muninn_prototype.modules.base_module import BaseModule
from muninn_prototype.modules.dataclasses.sensor_reading import SensorReading
from muninn_prototype.modules.optics_module import ImageFrame
from muninn_prototype.modules.topic_config import topic as configured_topic

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "tcp://*:5555"
_DEFAULT_SUIT_ID = "delta-default"
_DEFAULT_RECONNECT_DELAY_S = 10.0


def _configured_suit_id(configuration: dict[str, Any] | None) -> str:
    candidate = (configuration or {}).get("suit", {}).get("suitID")
    suit_id = str(candidate).strip() if candidate is not None else ""

    if suit_id:
        logger.debug("Using publisher suit ID %s", suit_id)
        return suit_id

    logger.debug(
        "No valid publisher suit ID configured; falling back to default: %s",
        _DEFAULT_SUIT_ID,
    )
    return _DEFAULT_SUIT_ID


def _configured_endpoint(configuration: dict[str, Any] | None) -> str:
    configuration = configuration or {}
    settings = configuration.get("egress", configuration.get("publisher", {}))
    candidate = settings.get("endpoint")
    endpoint = str(candidate).strip() if candidate is not None else ""

    if endpoint:
        logger.debug("Using publisher endpoint %s", endpoint)
        return endpoint

    logger.debug(
        "No valid publisher endpoint configured; falling back to default: %s",
        _DEFAULT_ENDPOINT,
    )
    return _DEFAULT_ENDPOINT


def _configured_reconnect_delay(configuration: dict[str, Any] | None) -> float:
    settings = (configuration or {}).get("egress", {})
    try:
        return max(
            0.0, float(settings.get("reconnect_delay_s", _DEFAULT_RECONNECT_DELAY_S))
        )
    except (TypeError, ValueError):
        logger.warning(
            "Invalid egress reconnect delay; using %.1f seconds",
            _DEFAULT_RECONNECT_DELAY_S,
        )
        return _DEFAULT_RECONNECT_DELAY_S


def _reading_to_payload(reading: SensorReading) -> dict[str, Any]:
    timestamp = reading.timestamp
    if isinstance(timestamp, datetime):
        timestamp_value = timestamp.isoformat()
    else:
        timestamp_value = str(timestamp)

    return {
        "reading_id": reading.reading_id,
        "timestamp": timestamp_value,
        "suit_id": reading.suit_id,
        "sensor_name": reading.sensor_name,
        "sensor_type": reading.sensor_type,
        "measurement": reading.measurement,
        "unit": reading.unit,
        "value": reading.value,
    }


class MessageEgressModule(BaseModule):
    def __init__(self):
        super().__init__()
        self._subscribed = False
        self._endpoint = _DEFAULT_ENDPOINT
        self._reconnect_delay_s = _DEFAULT_RECONNECT_DELAY_S
        self._suit_id = _DEFAULT_SUIT_ID
        self._publish_queue: queue.Queue[SensorReading | None] = queue.Queue(
            maxsize=1000
        )
        self._image_queue: queue.Queue[tuple[str, str, bytes] | None] = queue.Queue(
            maxsize=10
        )
        self._egress_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._egress_adapter: MessageEgressAdapter | None = None
        self._images_subscribed = False

    def _publish_loop(self) -> None:
        adapter = self._egress_adapter
        if adapter is None:
            logger.error("Failed to start egress because no adapter is configured")
            return
        readings_topic = f"{self._suit_id}/{configured_topic('readings')}"
        while not self._stop_event.is_set():
            try:
                adapter.connect(self._endpoint)
                logger.info("Connected egress adapter to %s", self._endpoint)
                while not self._stop_event.is_set():
                    try:
                        reading = self._publish_queue.get(timeout=0.1)
                        if reading is None:
                            return
                        adapter.publish(
                            readings_topic,
                            json.dumps(
                                _reading_to_payload(reading),
                                separators=(",", ":"),
                                default=str,
                            ),
                        )
                        logger.debug("Published reading %s", reading.reading_id)
                    except queue.Empty:
                        pass
                    try:
                        image = self._image_queue.get_nowait()
                        if image is None:
                            return
                        image_topic, metadata, payload = image
                        adapter.publish_multipart(image_topic, metadata, payload)
                    except queue.Empty:
                        pass
            except Exception:
                logger.exception(
                    "Publisher transport failed; retrying in %.1f seconds",
                    self._reconnect_delay_s,
                )
                adapter.close()
                if self._stop_event.wait(self._reconnect_delay_s):
                    break
            else:
                break
        adapter.close()

    def _on_reading(self, reading: SensorReading) -> None:
        try:
            self._publish_queue.put_nowait(reading)
        except queue.Full:
            logger.warning(
                "Dropping reading %s because the egress queue is full",
                reading.reading_id,
            )

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        self._suit_id = _configured_suit_id(configuration)
        self._endpoint = _configured_endpoint(configuration)
        self._reconnect_delay_s = _configured_reconnect_delay(configuration)
        self._egress_adapter = build_message_egress_adapter(configuration)

        if self._egress_adapter is None:
            logger.warning(
                "Egress will not publish because no egress adapter is available"
            )
            return
        if not self._subscribed:
            pub.subscribe(self._on_reading, configured_topic("readings"))
            self._subscribed = True
        if not self._images_subscribed:
            pub.subscribe(self._on_feed_image, configured_topic("images"))
            pub.subscribe(
                self._on_full_resolution_image,
                configured_topic("full_resolution_images"),
            )
            self._images_subscribed = True
        if self._egress_thread is None or not self._egress_thread.is_alive():
            self._stop_event.clear()
            self._egress_thread = threading.Thread(
                target=self._publish_loop,
                daemon=True,
                name="MessageEgressModule:ZeroMQ",
            )
            self._egress_thread.start()
        super().initiate()
        logger.info("Started message egress module for suit %s", self._suit_id)

    def _queue_image(
        self, topic_name: str, frame: ImageFrame, frame_id: int, **extra: Any
    ) -> None:
        metadata = json.dumps(
            {
                "frame_id": frame_id,
                "timestamp": frame.timestamp.isoformat(),
                "width": frame.width,
                "height": frame.height,
                "format": frame.format,
                **extra,
            },
            separators=(",", ":"),
        )
        try:
            self._image_queue.put_nowait(
                (f"{self._suit_id}/{topic_name}", metadata, frame.image)
            )
        except queue.Full:
            logger.warning(
                "Dropping image frame %s because the egress image queue is full",
                frame_id,
            )

    def _on_feed_image(self, frame: ImageFrame, frame_id: int = 0) -> None:
        self._queue_image(configured_topic("images"), frame, frame_id)

    def _on_full_resolution_image(
        self, frame: ImageFrame, frame_id: int = 0, path: str = ""
    ) -> None:
        self._queue_image(
            configured_topic("full_resolution_images"),
            frame,
            frame_id,
            kind="full_resolution",
            path=path,
        )

    def _on_image(self, frame: ImageFrame, frame_id: int = 0) -> None:
        try:
            self._queue_image(configured_topic("images"), frame, frame_id)
        except Exception:
            logger.exception("Failed to publish image frame %s", frame_id)

    def shutdown(self) -> None:
        self._stop_event.set()
        try:
            self._publish_queue.put_nowait(None)
        except queue.Full:
            logger.debug("Publisher queue was full while shutting down")
        try:
            self._image_queue.put_nowait(None)
        except queue.Full:
            logger.debug("Image queue was full while shutting down")

        thread = self._egress_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self._reconnect_delay_s + 1.0))
            if thread.is_alive():
                logger.error(
                    "Message egress worker did not stop within the shutdown timeout"
                )
            else:
                self._egress_thread = None

        if self._subscribed:
            pub.unsubscribe(self._on_reading, configured_topic("readings"))
            self._subscribed = False
        if self._images_subscribed:
            pub.unsubscribe(self._on_feed_image, configured_topic("images"))
            pub.unsubscribe(
                self._on_full_resolution_image,
                configured_topic("full_resolution_images"),
            )
            self._images_subscribed = False
