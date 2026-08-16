from . import (
    backup_module,
    command_module,
    communications_module,
    display_module,
    fan_module,
    message_egress_module,
    monitoring_module,
    optics_module,
)
from .adapters.bme680_sensor_adapter import BME680SensorAdapter
from .adapters.emc2101_sensor_adapter import EMC2101SensorAdapter
from .adapters.sensor_adapter import SensorAdapter
from .command_module import CommandModule
from .dataclasses.sensor_config import SensorConfig
from .dataclasses.sensor_reading import SensorReading
from .message_egress_module import MessageEgressModule
from .message_ingress_module import MessageIngressModule
from .sensor_module import SensorModule

_optics_module = optics_module.OpticsModule()

MODULES = [
    monitoring_module.MonitoringModule(),
    display_module.DisplayModule(),
    backup_module.BackupModule(),
    MessageEgressModule(),
    communications_module.CommunicationsModule(),
    MessageIngressModule(),
    _optics_module,
    fan_module.FanModule(),
    SensorModule(),
]

MODULES.append(CommandModule())
