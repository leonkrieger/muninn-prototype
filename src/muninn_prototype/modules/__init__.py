from . import analyzing_module
from . import audio_module
from . import backup_module
from . import command_module
from . import display_module
from . import optics_module
from . import publisher_module
from .sensor_module import SensorModule
from .adapters.bme680_sensor_adapter import BME680SensorAdapter
from .adapters.emc2101_sensor_adapter import EMC2101SensorAdapter
from .adapters.sensor_adapter import SensorAdapter
from .dataclasses.sensor_config import SensorConfig
from .dataclasses.sensor_reading import SensorReading

MODULES = [
    display_module.DisplayModule(),
    backup_module.BackupModule(),
    publisher_module.PublisherModule(),
#    analyzing_module.AnalyzingModule(),
#    audio_module,
#    command_module,
#    optics_module,
    SensorModule(),
]
