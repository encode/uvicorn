import asyncio
import websockets
import enum


class Headers:
    def __init__(self, raw_headers):
        self.raw_headers = raw_headers

    def get(self, key, default=None):
        get_key = key.lower().encode("latin-1")
        for raw_key, raw_value in self.raw_headers:
            if raw_key == get_key:
                return raw_value.decode("latin-1")
        return default

    def __setitem__(self, key, value):
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")
        for idx, (raw_key, raw_value) in enumerate(self.raw_headers):
            if raw_key == set_key:
                self.raw_headers[idx] = set_value
                return
        self.raw_headers.append((set_key, set_value))


def websocket_upgrade(http):
    request_headers = Headers(http.headers)
    response_headers = Headers([])

    try:
        key = websockets.handshake.check_request(request_headers)
        websockets.handshake.build_response(response_headers, key)
    except websockets.InvalidHandshake as exc:
        rv = b"HTTP/1.1 403 Forbidden\r\n\r\n"
        http.transport.write(rv)
        http.transport.close()
        return

    # Retrieve any subprotocols to be negotiated with the consumer later
    subprotocols = [
        subprotocol.strip()
        for subprotocol in request_headers.get("sec-websocket-protocol", "").split(",")
    ]
    http.scope.update({"type": "websocket", "subprotocols": subprotocols})
    asgi_instance = http.app(http.scope)
    request = WebSocketRequest(http, response_headers)
    http.loop.create_task(asgi_instance(request.receive, request.send))
    request.put_message({"type": "websocket.connect", "order": 0})


async def websocket_session(protocol):
    close_code = None
    order = 1
    request = protocol.active_request
    path = request.scope["path"]

    while True:
        try:
            data = await protocol.recv()
        except websockets.exceptions.ConnectionClosed as exc:
            close_code = exc.code
            break

        message = {
            "type": "websocket.receive",
            "path": path,
            "text": None,
            "bytes": None,
            "order": order,
        }
        if isinstance(data, str):
            message["text"] = data
        elif isinstance(data, bytes):
            message["bytes"] = data
        request.put_message(message)
        order += 1

    message = {
        "type": "websocket.disconnect",
        "code": close_code,
        "path": path,
        "order": order,
    }
    request.put_message(message)
    protocol.active_request = None


class WebSocketRequestState(enum.Enum):
    CONNECTING = 0
    CONNECTED = 1
    CLOSED = 2


class WebSocketRequest:
    def __init__(self, http, response_headers):
        self.state = WebSocketRequestState.CONNECTING
        self.http = http
        self.scope = http.scope
        self.response_headers = response_headers
        self.loop = asyncio.get_event_loop()
        self.receive_queue = asyncio.Queue()
        self.protocol = None

    def put_message(self, message):
        self.receive_queue.put_nowait(message)

    async def receive(self):
        return await self.receive_queue.get()

    async def send(self, message):
        message_type = message["type"]
        text_data = message.get("text")
        bytes_data = message.get("bytes")

        if self.state == WebSocketRequestState.CLOSED:
            raise Exception("Unexpected message, WebSocketRequest is CLOSED.")

        if self.state == WebSocketRequestState.CONNECTING:
            # Complete the handshake after negotiating a subprotocol with the consumer
            subprotocol = message.get("subprotocol", None)
            if subprotocol:
                self.response_headers["Sec-WebSocket-Protocol"] = subprotocol
            protocol = WebSocketProtocol(self.http, self.response_headers)
            protocol.connection_made(self.http.transport, subprotocol)
            protocol.connection_open()
            self.http.transport.set_protocol(protocol)
            self.protocol = protocol
            self.protocol.active_request = self

            if not self.protocol.accepted:
                accept = message_type == "websocket.accept"
                close = message_type == "websocket.close"

                if accept or close:
                    self.protocol.accept()
                    self.state = WebSocketRequestState.CONNECTED
                    if accept:
                        self.protocol.listen()
                else:
                    self.protocol.reject()
                    self.state = WebSocketRequestState.CLOSED

        if self.state == WebSocketRequestState.CONNECTED:
            if text_data:
                await self.protocol.send(text_data)
            elif bytes_data:
                await self.protocol.send(bytes_data)

            if message_type == "websocket.close":
                code = message.get("code", 1000)
                await self.protocol.close(code=code)
                self.state = WebSocketRequestState.CLOSED
        else:
            raise Exception("Unexpected message, WebSocketRequest is %s" % self.state)


class WebSocketProtocol(websockets.protocol.WebSocketCommonProtocol):
    def __init__(self, http, handshake_headers):
        super().__init__(max_size=10000000, max_queue=10000000)
        self.handshake_headers = handshake_headers
        self.accepted = False
        self.loop = http.loop
        self.app = http.app
        self.active_request = None

    def connection_made(self, transport, subprotocol):
        super().connection_made(transport)
        self.subprotocol = subprotocol
        self.transport = transport

    def accept(self):
        self.accepted = True
        rv = b"HTTP/1.1 101 Switching Protocols\r\n"
        for k, v in self.handshake_headers.raw_headers:
            rv += k + b": " + v + b"\r\n"
        rv += b"\r\n"
        self.transport.write(rv)

    def listen(self):
        self.loop.create_task(websocket_session(self))

    def reject(self):
        rv = b"HTTP/1.1 403 Forbidden\r\n\r\n"
        self.active_request = None
        self.transport.write(rv)
        self.transport.close()
