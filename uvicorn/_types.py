import sys
from typing import List, Optional, Tuple, Union

if sys.version_info < (3, 8):
    from typing_extensions import Literal, TypedDict
else:
    from typing import Literal
    from typing import TypedDict

from websockets import Subprotocol

# HTTP messages
# receive


class HTTPReceiveRequest(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#request-receive-event
    """

    type: Literal["http.request"]
    body: Optional[bytes]
    more_body: Optional[bool]


class HTTPReceiveDisconnect(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#disconnect-receive-event
    """

    type: Literal["http.disconnect"]


HTTPReceiveMessage = Union[HTTPReceiveRequest, HTTPReceiveDisconnect]

# send


class HTTPSendResponseStart(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#response-start-send-event
    """

    type: Literal["http.response.start"]
    status: int
    headers: Optional[List[Tuple[bytes, bytes]]]


class HTTPSendResponseBody(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#response-body-send-event
    """

    type: Literal["http.response.body"]
    body: Optional[bytes]
    more_body: Optional[bool]


HTTPSendMessage = Union[HTTPSendResponseBody, HTTPSendResponseStart]


# WS messages
# receive
class WSReceiveConnect(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#connect-receive-event
    """

    type: Literal["websocket.connect"]


class WSReceive(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#receive-receive-event
    """

    type: Literal["websocket.receive"]
    bytes: Optional[bytes]
    text: Optional[str]


class WSReceiveDisconnect(TypedDict):
    """
    yeah I know this link looks off but it is the one !
    https://asgi.readthedocs.io/en/latest/specs/www.html#id2
    """

    type: Literal["websocket.disconnect"]
    code: int


WSReceiveMessage = Union[WSReceiveConnect, WSReceive, WSReceiveDisconnect]

# send


class WSSendAccept(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#accept-send-event
    """

    type: Literal["websocket.accept"]
    subprotocol: Optional[Subprotocol]
    headers: Optional[List[Tuple[bytes, bytes]]]


class WSSend(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#send-send-event
    """

    type: Literal["websocket.send"]
    bytes: Optional[bytes]
    text: Optional[str]


class WSSendClose(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/www.html#close-send-event
    """

    type: Literal["websocket.close"]
    code: int


WSSendMessage = Union[WSSendAccept, WSSend, WSSendClose]

# ALL messages
ReceiveMessage = Union[HTTPReceiveMessage, WSReceiveMessage]
SendMessage = Union[HTTPSendMessage, WSSendMessage]
