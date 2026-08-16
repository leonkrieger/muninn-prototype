import logging
import inspect
import threading
import time
from pubsub import pub
from muninn_prototype.modules import MODULES
from muninn_prototype.modules.base_module import BaseModule
from muninn_prototype.modules.topic_config import topic
from muninn_prototype.config_validation import validate_configuration

logger = logging.getLogger(__name__)

_INITIALIZATION_OK_DISPLAY_S = 5.0

def on_heartbeat(module):
    logger.info(f"Received heartbeat from: {module}")


def _initiate_module(module, configuration: dict | None = None):
    initiate = getattr(module, "initiate", None)
    if initiate is None:
        return

    if len(inspect.signature(initiate).parameters) == 0:
        initiate()
        return

    initiate(configuration)

def initiate_suit(
    configuration: dict | None = None,
    shutdown_event: threading.Event | None = None,
):
    # Keep this guard here as well as in main(): callers may start the suit
    # directly and must receive the same fail-fast behavior.
    validated_configuration = validate_configuration(configuration)
    configuration = validated_configuration.model_dump()
    logger.info("Initiating suit ...")

    heartbeat_interval_s = float((configuration or {}).get("heartbeat", {}).get("hb_freq_s", 10.0))
    initialization_failed = False

    monitoring_module = next(
        (module for module in MODULES if module.__class__.__name__ == "MonitoringModule"),
        None,
    )
    if monitoring_module is not None:
        monitoring_module.configure_expected_modules(
            [module.__class__.__name__ for module in MODULES]
        )

    def on_initialization_error(message=None, status=None, error_code=None, **_):
        nonlocal initialization_failed
        initialization_failed = True
        logger.error("Module initialization reported an error: %s", error_code)

    # Subscribe before starting modules so errors raised during initiation are
    # captured before the success message is considered.
    pub.subscribe(on_initialization_error, topic("errors"))

    started_modules = []
    try:
        for index, module in enumerate(MODULES):
            if shutdown_event is not None and shutdown_event.is_set():
                raise RuntimeError("Suit initialization cancelled")
            if isinstance(module, BaseModule):
                module.configure_heartbeat_interval(heartbeat_interval_s)

            started_modules.append(module)
            _initiate_module(module, configuration)

            if initialization_failed:
                raise RuntimeError("A suit module reported an initialization error")

            # DisplayModule is first in MODULES, so it is ready to receive INIT
            # before the rest of the suit is initialized.
            if index == 0:
                pub.sendMessage(topic("display"), text="INIT")

        pub.sendMessage(topic("display"), text="INOK")
        pub.subscribe(on_heartbeat, topic("heartbeats"))
        if shutdown_event is not None:
            if shutdown_event.wait(_INITIALIZATION_OK_DISPLAY_S):
                raise RuntimeError("Suit initialization cancelled")
        else:
            time.sleep(_INITIALIZATION_OK_DISPLAY_S)
        pub.sendMessage(topic("display"), text="    ")
        logger.info("Suit initiated")
    except Exception as error:
        logger.exception("Suit startup refused because initialization failed")
        for module in reversed(started_modules):
            shutdown = getattr(module, "shutdown", None)
            if shutdown is None:
                continue
            try:
                shutdown()
                if isinstance(module, BaseModule):
                    BaseModule.shutdown(module)
            except Exception:
                logger.exception("Failed to roll back %s", module.__class__.__name__)
        raise RuntimeError("Suit initialization failed; startup refused") from error
    finally:
        pub.unsubscribe(on_initialization_error, topic("errors"))


def shutdown_suit() -> None:
    """Stop modules in reverse startup order."""
    logger.info("Shutting down suit modules")
    for module in reversed(MODULES):
        shutdown = getattr(module, "shutdown", None)
        if shutdown is None:
            continue
        try:
            shutdown()
            if isinstance(module, BaseModule):
                BaseModule.shutdown(module)
        except Exception:
            logger.exception("Failed to shut down %s", module.__class__.__name__)
