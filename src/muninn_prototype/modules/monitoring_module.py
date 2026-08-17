from __future__ import annotations

import logging
import threading
import time
from typing import Any

from pubsub import pub

from muninn_prototype.modules.base_module import BaseModule

from .topic_config import topic

logger = logging.getLogger(__name__)


class MonitoringModule(BaseModule):
    """Monitor module heartbeats and sensor readings."""

    def __init__(self) -> None:
        super().__init__()
        self._expected_modules: set[str] = set()
        self._last_heartbeat: dict[str, float | None] = {}
        self._unhealthy: set[str] = set()
        self._allowed_missed_heartbeats = 1
        self._check_interval_s = 10.0
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._subscribed = False
        self._sensor_checks: dict[
            tuple[str, str], list[tuple[float | None, float | None]]
        ] = {}
        self._sensor_warnings: set[tuple[str, str]] = set()
        self._sensor_last_reading: dict[str, float] = {}
        self._sensor_unhealthy: set[str] = set()
        self._sensor_poll_intervals: dict[str, float] = {}

    def _on_reading(self, reading: Any) -> None:
        now = time.monotonic()
        sensor_name = str(reading.sensor_name)
        with self._lock:
            self._sensor_last_reading[sensor_name] = now
            recovered = sensor_name in self._sensor_unhealthy
            if recovered:
                self._sensor_unhealthy.remove(sensor_name)

        if recovered:
            pub.sendMessage(
                "warning",
                module=sensor_name,
                message=f"Sensor {sensor_name} readings resumed",
                recovered=True,
                missed_heartbeats=0,
                allowed_missed_heartbeats=self._allowed_missed_heartbeats,
            )

        key = (reading.sensor_name, reading.measurement)
        with self._lock:
            checks = tuple(self._sensor_checks.get(key, ()))
        try:
            value = float(reading.value)
        except (TypeError, ValueError):
            return

        violated = any(
            (minimum is not None and value < minimum)
            or (maximum is not None and value > maximum)
            for minimum, maximum in checks
        )
        with self._lock:
            was_violated = key in self._sensor_warnings
            if violated:
                self._sensor_warnings.add(key)
            elif was_violated:
                self._sensor_warnings.remove(key)

        if not violated and not was_violated:
            return

        limits = []
        for minimum, maximum in checks:
            if minimum is not None:
                limits.append(f"min {minimum}")
            if maximum is not None:
                limits.append(f"max {maximum}")
        recovered = not violated
        pub.sendMessage(
            "warning",
            module=reading.sensor_name,
            measurement=reading.measurement,
            value=reading.value,
            message=(
                f"Sensor {reading.sensor_name} {reading.measurement} value "
                f"{reading.value} {reading.unit} "
                f"{'recovered within' if recovered else 'exceeds'} {' and '.join(limits)}"
            ),
            recovered=recovered,
            missed_heartbeats=0,
            allowed_missed_heartbeats=self._allowed_missed_heartbeats,
        )

    def configure_expected_modules(self, module_names: list[str]) -> None:
        """Provide the module roster before monitoring starts."""
        with self._lock:
            self._expected_modules = {
                name
                for name in module_names
                if name and name != self.__class__.__name__
            }
            self._last_heartbeat = {
                name: self._last_heartbeat.get(name) for name in self._expected_modules
            }

    def _on_heartbeat(self, module: str) -> None:
        now = time.monotonic()
        with self._lock:
            if module not in self._expected_modules:
                return
            self._last_heartbeat[module] = now
            recovered = module in self._unhealthy
            if recovered:
                self._unhealthy.remove(module)

        if recovered:
            pub.sendMessage(
                "warning",
                module=module,
                message=f"Module {module} recovered heartbeat reporting",
                recovered=True,
                missed_heartbeats=0,
                allowed_missed_heartbeats=self._allowed_missed_heartbeats,
            )

    def _publish_outage(self, module: str, missed: int) -> None:
        pub.sendMessage(
            "warning",
            module=module,
            message=f"Module {module} missed {missed} heartbeats",
            recovered=False,
            missed_heartbeats=missed,
            allowed_missed_heartbeats=self._allowed_missed_heartbeats,
        )

    def _check_health(self) -> None:
        now = time.monotonic()
        outages: list[tuple[str, int]] = []
        sensor_outages: list[tuple[str, float]] = []
        with self._lock:
            for module in self._expected_modules:
                last = self._last_heartbeat.get(module)
                elapsed = (now - last) if last is not None else now - self._started_at
                missed = max(0, int(elapsed // self._check_interval_s) - 1)
                if (
                    missed > self._allowed_missed_heartbeats
                    and module not in self._unhealthy
                ):
                    self._unhealthy.add(module)
                    outages.append((module, missed))

            for sensor_name, last_reading in self._sensor_last_reading.items():
                poll_interval = self._sensor_poll_intervals.get(sensor_name)
                if poll_interval is None:
                    continue
                overdue_by = now - last_reading
                # Allow one missed polling interval before reporting an outage.
                if overdue_by > poll_interval * 2 and sensor_name not in self._sensor_unhealthy:
                    self._sensor_unhealthy.add(sensor_name)
                    sensor_outages.append((sensor_name, overdue_by))

        for module, missed in outages:
            logger.warning("Module %s missed %d heartbeats", module, missed)
            self._publish_outage(module, missed)

        for sensor_name, overdue_by in sensor_outages:
            logger.warning(
                "Sensor %s has not produced a reading for %.1f seconds",
                sensor_name,
                overdue_by,
            )
            pub.sendMessage(
                "warning",
                module=sensor_name,
                message=(
                    f"Sensor {sensor_name} readings are overdue by "
                    f"{overdue_by:.1f} seconds"
                ),
                recovered=False,
                missed_heartbeats=0,
                allowed_missed_heartbeats=self._allowed_missed_heartbeats,
            )

    def _monitor(self) -> None:
        while not self._stop_event.wait(self._check_interval_s):
            self._check_health()

    def initiate(self, configuration: dict[str, Any] | None = None) -> None:
        configuration = configuration or {}
        settings = (configuration or {}).get("monitoring", {})
        self._allowed_missed_heartbeats = max(
            0, int(settings.get("allowed_missed_heartbeats", 1))
        )
        self._check_interval_s = max(
            0.1,
            float((configuration or {}).get("heartbeat", {}).get("hb_freq_s", 10.0)),
        )
        self._started_at = time.monotonic()
        self._sensor_checks = {}
        self._sensor_warnings.clear()
        self._sensor_last_reading.clear()
        self._sensor_unhealthy.clear()
        self._sensor_poll_intervals = {}
        for sensor in configuration.get("sensors", []):
            sensor_name = str(sensor.get("name", "")).strip()
            try:
                poll_hz = float(sensor.get("poll_hz", 0))
                if sensor_name and poll_hz > 0:
                    self._sensor_poll_intervals[sensor_name] = 1.0 / poll_hz
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid polling frequency for %s", sensor_name)
            for check in sensor.get("checks", []):
                measurement = str(check.get("measurement", "")).strip()
                if not sensor_name or not measurement:
                    continue
                minimum = check.get("min")
                maximum = check.get("max")
                if minimum is None and maximum is None:
                    logger.warning(
                        "Ignoring empty check for %s/%s", sensor_name, measurement
                    )
                    continue
                try:
                    bounds = (
                        None if minimum is None else float(minimum),
                        None if maximum is None else float(maximum),
                    )
                except (TypeError, ValueError):
                    logger.warning(
                        "Ignoring invalid check for %s/%s", sensor_name, measurement
                    )
                    continue
                self._sensor_checks.setdefault((sensor_name, measurement), []).append(
                    bounds
                )
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            logger.debug("Monitoring worker is already running")
            return
        self._stop_event.clear()
        if not self._subscribed:
            pub.subscribe(self._on_heartbeat, topic("heartbeats"))
            pub.subscribe(self._on_reading, topic("readings"))
            self._subscribed = True
        self._monitor_thread = threading.Thread(
            target=self._monitor,
            daemon=True,
            name="MonitoringModule:Heartbeat",
        )
        self._monitor_thread.start()
        logger.info("Monitoring module started")

    def shutdown(self) -> None:
        self._stop_event.set()
        thread = self._monitor_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, self._check_interval_s + 1.0))
        if self._subscribed:
            pub.unsubscribe(self._on_heartbeat, topic("heartbeats"))
            pub.unsubscribe(self._on_reading, topic("readings"))
            self._subscribed = False
