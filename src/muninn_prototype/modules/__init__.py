from . import analyzing_module
from . import communications_module
from . import backup_module
from . import command_module
from .message_ingress_module import MessageIngressModule
from . import display_module
from . import optics_module
from . import fan_module
from . import message_egress_module
from .message_egress_module import MessageEgressModule
from . import monitoring_module
from .sensor_module import SensorModule
from .adapters.bme680_sensor_adapter import BME680SensorAdapter
from .adapters.emc2101_sensor_adapter import EMC2101SensorAdapter
from .adapters.sensor_adapter import SensorAdapter
from .dataclasses.sensor_config import SensorConfig
from .dataclasses.sensor_reading import SensorReading

MODULES = [
    monitoring_module.MonitoringModule(),
    display_module.DisplayModule(),
    backup_module.BackupModule(),
    MessageEgressModule(),
#   analyzing_module.AnalyzingModule(),
    communications_module.CommunicationsModule(),
    MessageIngressModule(),
    optics_module.OpticsModule(),
    fan_module.FanModule(),
    SensorModule(),
]
