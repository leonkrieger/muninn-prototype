from . import analyzing_module
from . import audio_module
from . import backup_module
from . import command_module
from . import optics_module
from . import publisher_module
from . import sensor_module

MODULES = [
    analyzing_module.AnalyzingModule(),
    audio_module,
    backup_module,
    command_module,
    optics_module,
    publisher_module,
    sensor_module.SensorModule(),
]