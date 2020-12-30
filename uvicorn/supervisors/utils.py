import logging
from multiprocessing.synchronize import Event as MEvent

logger = logging.getLogger("uvicorn.error")


async def raise_shutdown(shutdown_event) -> None:
    logger.info("going to await shutdown")
    await shutdown_event()
    logger.info("will raise shutdown")
    raise Shutdown()


async def check_multiprocess_shutdown_event(shutdown_event: MEvent, sleep) -> None:
    while True:
        if shutdown_event.is_set():
            logger.debug("multiprocessing event set")
            return
        await sleep(0.1)


class Shutdown(Exception):
    pass
