from uvicorn.lifespan.off import LifespanOff
from uvicorn.lifespan.on import LifespanOn


def LifespanAuto(config):
    if not config.loaded:
        config.load()

    if not config.loop_setup:
        config.setup_event_loop()

    try:
        config.loaded_app({"type": "lifespan"})
    except BaseException as exc:
        config.logger_instance.debug(
            "Lifespan protocol is not recognized by the application."
        )
        return LifespanOff(config)
    else:
        return LifespanOn(config)
