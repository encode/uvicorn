import ssl
from typing import List, Literal

HTTPProtocolType = Literal["auto", "h11", "httptools"]
WSProtocolType = Literal["auto", "none", "websockets", "wsproto"]
LifespanType = Literal["auto", "on", "off"]
LoopSetupType = Literal["none", "auto", "asyncio", "uvloop"]
InterfaceType = Literal["auto", "asgi3", "asgi2", "wsgi"]

INTERFACES: List[InterfaceType] = ["auto", "asgi3", "asgi2", "wsgi"]

SSL_PROTOCOL_VERSION: int = ssl.PROTOCOL_TLS_SERVER
