"""Validation for ``config/defaults.toml``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ConfigurationError(ValueError):
    """A configuration cannot be used to start Muninn."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SuitConfig(StrictModel):
    suitID: str = Field(min_length=1)


class EgressConfig(StrictModel):
    pub_backend: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    reconnect_delay_s: float = Field(ge=0)


class IngressConfig(StrictModel):
    transport: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    topic: str


class LoggingConfig(StrictModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class DisplayConfig(StrictModel):
    adapter: Literal["qwiic", "qwiic_alphanumeric"]


class HeartbeatConfig(StrictModel):
    hb_freq_s: float = Field(gt=0)


class MonitoringConfig(StrictModel):
    allowed_missed_heartbeats: int = Field(ge=0)


class CommunicationsConfig(StrictModel):
    enabled: bool
    executable: str
    config_path: str
    restart_delay_s: float = Field(ge=0)
    startup_grace_s: float = Field(ge=0)


class OpticsConfig(StrictModel):
    enabled: bool
    feed_fps: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    jpeg_quality: int = Field(ge=1, le=100)
    save_feed_images: bool


class ImageRetentionConfig(StrictModel):
    feed_priority: int = Field(ge=0, le=99)
    full_resolution_priority: int = Field(ge=0, le=99)


class RetentionConfig(StrictModel):
    policy: Literal["keep_oldest", "keep_newest", "keep_highest_priority", "prune"]
    high_watermark_percent: float = Field(ge=0, le=100)
    low_watermark_percent: float = Field(ge=0, le=100)
    minimum_free_bytes: int = Field(ge=0)
    prune_every: int = Field(ge=0)
    images: ImageRetentionConfig

    @model_validator(mode="after")
    def valid_watermarks(self) -> RetentionConfig:
        if self.low_watermark_percent >= self.high_watermark_percent:
            raise ValueError(
                "low_watermark_percent must be less than high_watermark_percent"
            )
        if self.policy == "prune" and self.prune_every < 2:
            raise ValueError("prune_every must be at least 2 when policy is prune")
        return self


class BackupConfig(StrictModel):
    csv_path: str = Field(min_length=1)
    partition: Literal["day"]
    retention: RetentionConfig


class FanConfig(StrictModel):
    enabled: bool
    i2c_address: int = Field(ge=0, le=127)
    normal_speed: int = Field(ge=0, le=100)


class SensorCheckConfig(StrictModel):
    measurement: str = Field(min_length=1)
    min: float
    max: float

    @model_validator(mode="after")
    def valid_range(self) -> SensorCheckConfig:
        if self.min >= self.max:
            raise ValueError("min must be less than max")
        return self


class SensorConfig(StrictModel):
    name: str = Field(min_length=1)
    sensor: str = Field(min_length=1)
    poll_hz: float = Field(gt=0, le=10)
    priority: int = Field(ge=0, le=99)
    i2c_address: int = Field(default=0x77, ge=0, le=127)
    checks: list[SensorCheckConfig] = []


class Configuration(StrictModel):
    suit: SuitConfig
    egress: EgressConfig
    ingress: IngressConfig
    logging: LoggingConfig
    display: DisplayConfig
    heartbeat: HeartbeatConfig
    monitoring: MonitoringConfig
    communications: CommunicationsConfig
    optics: OpticsConfig
    backup: BackupConfig
    fan: FanConfig
    sensors: list[SensorConfig]

    @model_validator(mode="after")
    def unique_sensor_names(self) -> Configuration:
        names = [sensor.name for sensor in self.sensors]
        if len(names) != len(set(names)):
            raise ValueError("sensor names must be unique")
        return self


def validate_configuration(configuration: dict) -> Configuration:
    """Validate raw TOML and return a typed immutable-by-convention model."""
    try:
        return Configuration.model_validate(configuration)
    except ValidationError as error:
        raise ConfigurationError(f"Invalid configuration:\n{error}") from error
