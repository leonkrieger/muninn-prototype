from __future__ import annotations

import argparse
import base64
import json
import logging
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path

import zmq

LOG = logging.getLogger("muninn.zeromq_collector")
IMAGE_TOPICS = {
    "image",
    "images",
    "camera",
    "frame",
    "frames",
    "full_resolution_images",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _image_extension(data: bytes, declared: str | None = None) -> str:
    declared = (declared or "").lower()
    if "png" in declared or data.startswith(b"\x89PNG"):
        return ".png"
    if "webp" in declared or data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if "gif" in declared or data.startswith(b"GIF8"):
        return ".gif"
    return ".jpg" if data.startswith(b"\xff\xd8\xff") else ".bin"


def _topic_kind(topic: str) -> str:
    return topic.rsplit("/", 1)[-1].lower()


class Collector:
    def __init__(self, endpoint: str, output: Path, subscriptions: list[str]) -> None:
        self.endpoint, self.output = endpoint, output
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.linger = 0
        self.socket.connect(endpoint)
        for prefix in subscriptions:
            self.socket.setsockopt_string(zmq.SUBSCRIBE, prefix)
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / "telemetry.jsonl").touch(exist_ok=True)
        self.stop_event = threading.Event()

    def _save_image(
        self, topic: str, payload: bytes, declared: str | None = None
    ) -> None:
        stamp = _now()
        folder = self.output / "images" / stamp.strftime("%Y-%m-%d")
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{stamp.strftime('%Y%m%dT%H%M%S.%fZ')}_{abs(hash(topic)) & 0xFFFF:04x}{_image_extension(payload, declared)}"
        (folder / filename).write_bytes(payload)
        LOG.info("Saved image %s (%d bytes)", folder / filename, len(payload))

    def _handle(self, topic_bytes: bytes, payload: bytes) -> None:
        topic = topic_bytes.decode("utf-8", errors="replace")
        kind = _topic_kind(topic)
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = None

        if kind in IMAGE_TOPICS or (
            isinstance(value, dict)
            and ("image" in value or "data" in value and "mime_type" in value)
        ):
            if isinstance(value, dict):
                encoded = value.get("image", value.get("data"))
                payload = (
                    base64.b64decode(encoded) if isinstance(encoded, str) else payload
                )
                self._save_image(topic, payload, value.get("mime_type"))
            else:
                self._save_image(topic, payload)
            return

        record = {
            "received_at": _now().isoformat(),
            "topic": topic,
            "payload": value
            if value is not None
            else {"raw_base64": base64.b64encode(payload).decode("ascii")},
        }
        with (self.output / "telemetry.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":"), default=str) + "\n")

    def run(self) -> None:
        LOG.info("Listening on %s; writing to %s", self.endpoint, self.output)
        try:
            poller = zmq.Poller()
            poller.register(self.socket, zmq.POLLIN)
            while not self.stop_event.is_set():
                events = dict(poller.poll(500))
                if self.socket not in events:
                    continue
                parts = self.socket.recv_multipart()
                if len(parts) < 2:
                    LOG.warning("Ignoring message with %d frame(s)", len(parts))
                    continue
                self._handle(parts[0], parts[-1])
        finally:
            self.socket.close()
            self.context.term()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect ZeroMQ telemetry and images from a suit"
    )
    parser.add_argument(
        "--endpoint", default="tcp://127.0.0.1:5555", help="ZeroMQ publisher endpoint"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("collected-data"), help="Output directory"
    )
    parser.add_argument(
        "--subscribe",
        action="append",
        default=[""],
        help="Topic prefix; repeatable (default: all topics)",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    collector = Collector(args.endpoint, args.output, args.subscribe)
    signal.signal(signal.SIGINT, lambda *_: collector.stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: collector.stop_event.set())
    collector.run()


if __name__ == "__main__":
    main()
