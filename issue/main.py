import asyncio
import gc
import logging

from fastapi import FastAPI
from memory_profiler import memory_usage

FORMAT = "%(asctime)-15s %(message)s"
logging.basicConfig(format=FORMAT)

logger = logging.getLogger("test.mem")
logger.setLevel(logging.INFO)

app = FastAPI(
    title="MemTest",
    description="MemTest",
    version="0.0.1",
)


async def print_mem():
    while True:
        await asyncio.sleep(2)
        mem_usage = memory_usage(-1, interval=0.2, timeout=1)
        logger.info(mem_usage)
        logger.info(f"Number of unreachable objects {gc.collect()}")


@app.on_event("startup")
async def on_startup():
    asyncio.gather(print_mem())
