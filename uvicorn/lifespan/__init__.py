from typing import Union
from uvicorn.lifespan.off import LifespanOff
from uvicorn.lifespan.on import LifespanOn

Lifespan = Union[LifespanOff, LifespanOn]
