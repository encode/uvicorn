import h2.connection
import h2.errors
import h2.events
import h2.exceptions
import io
import http
import time
import asyncio
import logging
import collections
from urllib.parse import unquote
from email.utils import formatdate

_StreamRequest = collections.namedtuple("_StreamRequest", ("headers", "scope", "cycle"))


def _get_default_headers():
    current_time = time.time()
    current_date = formatdate(current_time, usegmt=True).encode()
    return (("server", "uvicorn"), ("date", current_date))


def _get_status_phrase(status_code):
    try:
        return http.HTTPStatus(status_code).phrase.encode()
    except ValueError as exc:
        return b""


DEFAULT_HEADERS = _get_default_headers()

HIGH_WATER_LIMIT = 65536


class FlowControl:
    def __init__(self, transport):
        self._transport = transport
        self.read_paused = False
        self.write_paused = False
        self._is_writable_event = asyncio.Event()
        self._is_writable_event.set()

    async def drain(self):
        await self._is_writable_event.wait()

    def pause_reading(self):
        if not self.read_paused:
            self.read_paused = True
            self._transport.pause_reading()

    def resume_reading(self):
        if self.read_paused:
            self.read_paused = False
            self._transport.resume_reading()

    def pause_writing(self):
        if not self.write_paused:
            self.write_paused = True
            self._is_writable_event.clear()

    def resume_writing(self):
        if self.write_paused:
            self.write_paused = False
            self._is_writable_event.set()


class ServiceUnavailable:
    def __init__(self, scope):
        pass

    async def __call__(self, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"Service Unavailable"})


class H2Protocol(asyncio.Protocol):
    http2 = True

    def __init__(
        self,
        app,
        loop=None,
        connections=None,
        tasks=None,
        state=None,
        logger=None,
        access_log=None,
        ws_protocol_class=None,
        root_path="",
        limit_concurrency=None,
        timeout_keep_alive=5,
    ):
        self.app = app
        self.loop = loop or asyncio.get_event_loop()
        self.connections = set() if connections is None else connections
        self.tasks = set() if tasks is None else tasks
        self.state = {"total_requests": 0} if state is None else state
        self.logger = logger or logging.getLogger("uvicorn")
        self.access_log = access_log and (self.logger.level <= logging.INFO)
        self.conn = h2.connection.H2Connection(
            config=h2.config.H2Configuration(client_side=False, header_encoding=None)
        )
        self.ws_protocol_class = ws_protocol_class
        self.root_path = root_path
        self.limit_concurrency = limit_concurrency

        # Timeouts
        self.timeout_keep_alive_task = None
        self.timeout_keep_alive = timeout_keep_alive

        # Per-connection state
        self.transport = None
        self.flow = None
        self.server = None
        self.client = None
        self.scheme = None

        # Per-request state
        self.scope = None
        self.headers = None
        self.streams = {}
        self.message_event = asyncio.Event()

    @classmethod
    def tick(cls):
        global DEFAULT_HEADERS
        DEFAULT_HEADERS = _get_default_headers()

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport
        self.flow = FlowControl(transport)
        self.server = transport.get_extra_info("sockname")
        self.client = transport.get_extra_info("peername")
        self.scheme = "https" if transport.get_extra_info("sslcontext") else "http"

        self.logger.debug("connection made, tranport %s", dir(transport))
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())
        self.logger.debug("%s - Connected", self.client[0])

    def connection_lost(self, exc):
        self.logger.debug("%s - Disconnected", self.client[0])

        for stream_id, stream in self.streams.items():
            if stream.cycle and not stream.cycle.response_complete:
                stream.cycle.disconnected = True

        # TODO: send close

        self.logger.debug("Disconnected, current streams: %s", self.streams)
        self.logger.debug("Exc", exc_info=exc)
        self.streams = {}
        self.message_event.set()

    def eof_received(self):
        self.streams = {}
        self.logger.debug("eof received, current streams: %s", self.streams)

    def data_received(self, data):
        if self.timeout_keep_alive_task is not None:
            self.timeout_keep_alive_task.cancel()
            self.timeout_keep_alive_task = None

        try:
            events = self.conn.receive_data(data)
        except h2.exceptions.ProtocolError:
            self.transport.write(self.conn.data_to_send())
            self.transport.close()
        else:
            self.transport.write(self.conn.data_to_send())
            for event in events:
                if isinstance(event, h2.events.RequestReceived):
                    self.on_request_received(event)
                elif isinstance(event, h2.events.DataReceived):
                    self.on_data_received(event)
                elif isinstance(event, h2.events.StreamEnded):
                    self.on_stream_ended(event)
                elif isinstance(event, h2.events.ConnectionTerminated):
                    self.on_connection_terminated(event)
                else:
                    self.logger.debug("Unhandled event %s.", event)

                self.transport.write(self.conn.data_to_send())

    def on_request_received(self, event):
        self.headers = []
        self.scope = dict(
            headers=self.headers,
            http_version="2",
            server=self.server,
            client=self.client,
            root_path=self.root_path,
            type="http",
            extensions={"http.response.push": {}},
        )
        scope_mapping = {
            b":scheme": "scheme",
            b":authority": "authority",
            b":method": "method",
            b":path": "path",
        }
        stream_id = event.stream_id
        for key, value in event.headers:
            if key in scope_mapping:
                self.scope[scope_mapping[key]] = value.decode("ascii")
            else:
                lower_key = key.lower()
                if lower_key == "connection":
                    tokens = [
                        token.lower().strip().decode("ascii")
                        for token in value.split(b",")
                    ]
                    if "upgrade" in tokens:
                        self.handle_upgrade(event)
                        return
                self.scope["headers"].append((lower_key, value))

        path, _, query_string = self.scope["path"].partition("?")
        self.scope["path"], self.scope["query_string"] = (
            unquote(path),
            query_string.encode("ascii"),
        )

        self.logger.debug("Request received, current scope %s", self.scope)
        self.logger.debug("Request received, current headers %s", self.scope["headers"])

        cycle = RequestResponseCycle(
            scope=self.scope,
            conn=self.conn,
            transport=self.transport,
            flow=self.flow,
            stream_id=stream_id,
            logger=self.logger,
            access_log=self.access_log,
            message_event=self.message_event,
            on_response=self.on_response_complete,
            on_request=self.on_request_received,
        )
        self.streams[stream_id] = _StreamRequest(
            headers=self.scope["headers"], scope=self.scope, cycle=cycle
        )
        self.logger.debug(
            "On request received, current %s, streams: %s", stream_id, self.streams
        )

        # Handle 503 responses when 'limit_concurrency' is exceeded.
        if self.limit_concurrency is not None and (
            len(self.connections) >= self.limit_concurrency
            or len(self.tasks) >= self.limit_concurrency
        ):
            message = "Exceeded concurrency limit."
            self.logger.warning(message)
            app = ServiceUnavailable
        else:
            app = self.app

        def cleanup(task):
            self.streams.pop(stream_id)

        task = self.loop.create_task(self.streams[stream_id].cycle.run_asgi(app))
        task.add_done_callback(self.tasks.discard)
        # task.add_done_callback(cleanup)
        task.add_done_callback(
            lambda t: self.logger.debug(
                "task done StreamID(%s), path %s", stream_id, self.scope["path"]
            )
        )
        self.tasks.add(task)

    def on_data_received(self, event):
        stream_id = event.stream_id
        self.logger.debug(
            "On data received, current %s, streams: %s", stream_id, self.streams
        )
        try:
            self.streams[stream_id].cycle.body += event.data
        except KeyError:
            self.conn.reset_stream(
                stream_id, error_code=h2.errors.ErrorCodes.PROTOCOL_ERROR
            )
        else:
            body_size = self.streams[stream_id].body.getbuffer().nbytes
            if body_size > HIGH_WATER_LIMIT:
                self.flow.pause_reading()
            self.message_event.set()

    def on_stream_ended(self, event):
        stream_id = event.stream_id
        self.logger.debug(
            "On stream ended, current %s, streams: %s", stream_id, self.streams
        )
        try:
            stream = self.streams[stream_id]
        except KeyError:
            # TODO: error code
            self.conn.reset_stream(
                stream_id, error_code=h2.errors.ErrorCodes.PROTOCOL_ERROR
            )
        else:
            self.transport.resume_reading()
            stream.cycle.more_body = False
            self.message_event.set()

    def on_connection_terminated(self, event):
        stream_id = event.stream_id
        self.logger.debug(
            "On connection terminated, current %s, streams: %s", stream_id, self.streams
        )
        self.streams.pop(stream_id).cycle.disconnected = True
        self.conn.close_cconnection(last_stream_id=stream_id)
        self.transport.write(self.conn.data_to_send())
        self.transport.close()

    def handle_upgrade(self, event):
        upgrade_value = None

    def shutdown(self):
        self.logger.debug("Shutdown. streams: %s, tasks: %s", self.streams, self.tasks)
        if self.streams:
            for stream_id, stream in self.streams.items():
                if stream.cycle.response_complete:
                    self.conn.close_cconnection(last_stream_id=stream_id)
                    self.transport.write(self.conn.data_to_send())
                else:
                    stream.cycle.keep_alive = False
            self.streams = {}

    def pause_writing(self):
        """
        Called by the transport when the write buffer exceeds the high water mark.
        """
        self.flow.pause_writing()

    def resume_writing(self):
        """
        Called by the transport when the write buffer drops below the low water mark.
        """
        self.flow.resume_writing()

    def timeout_keep_alive_handler(self):
        """
        Called on a keep-alive connection if no new data is received after a short delay.
        """
        if not self.transport.is_closing():
            for stream_id, stream in self.streams.items():
                self.conn.close_connection(last_stream_id=stream_id)
                self.transport.write(self.conn.data_to_send())
            self.transport.close()

    def on_response_complete(self):
        self.state["total_requests"] += 1

        if self.transport.is_closing():
            return

        # Set a short Keep-Alive timeout.
        self.timeout_keep_alive_task = self.loop.call_later(
            self.timeout_keep_alive, self.timeout_keep_alive_handler
        )

        # Unpause data reads if needed.
        self.flow.resume_reading()


class RequestResponseCycle:
    def __init__(
        self,
        scope,
        conn,
        transport,
        flow,
        logger,
        access_log,
        stream_id,
        message_event,
        on_response,
        on_request,
    ):
        self.scope = scope
        self.conn = conn
        self.transport = transport
        self.flow = flow
        self.logger = logger
        self.access_log = access_log
        self.message_event = message_event
        self.on_response = on_response
        self.on_request = on_request
        self.stream_id = stream_id

        # Connection state
        self.disconnected = False
        self.keep_alive = True

        # Request state
        self.body = b""
        self.more_body = True

        # Response state
        self.response_started = False
        self.response_complete = False

    # ASGI exception wrapper
    async def run_asgi(self, app):
        try:
            asgi = app(self.scope)
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application"
            self.logger.error(msg, exc_info=True)
            if not self.response_started:
                await self.send_500_response()
            else:
                self.transport.close()
        else:
            if result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.logger.error(msg, result)
                self.transport.close()
            elif not self.response_started and not self.disconnected:
                msg = "ASGI callable returned without starting response."
                self.logger.error(msg)
                await self.send_500_response()
            elif not self.response_complete and not self.disconnected:
                msg = "ASGI callable returned without completing response."
                self.logger.error(msg)
                self.transport.close()
        finally:
            self.on_response = None

    async def send_500_response(self):
        await self.send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"connection", b"close"),
                ],
            }
        )
        await self.send(
            {"type": "http.response.body", "body": b"Internal Server Error"}
        )

    # ASGI interface
    async def send(self, message):
        global DEFAULT_HEADERS

        message_type = message["type"]

        if self.disconnected:
            return

        if self.flow.write_paused:
            await self.flow.drain()

        if not self.response_started:
            # Sending response status line and headers
            if message_type != "http.response.start":
                msg = "Expected ASGI message 'http.response.start', but got '%s'."
                raise RuntimeError(msg % message_type)

            self.response_started = True

            status_code = message["status"]
            headers = (*DEFAULT_HEADERS, *message.get("headers", ()))

            if self.access_log:
                self.logger.info(
                    '%s - "%s %s HTTP/%s" %d',
                    self.scope["client"][0],
                    self.scope["method"],
                    self.scope["path"],
                    self.scope["http_version"],
                    status_code,
                )

            # Write response status line and headers
            headers = ((":status", str(status_code)), *headers)
            self.logger.debug("response start, message %s", message)
            self.conn.send_headers(self.stream_id, headers, end_stream=False)
            self.transport.write(self.conn.data_to_send())

        elif not self.response_complete:
            # Sending response body
            if message_type == "http.response.body":

                more_body = message.get("more_body", False)

                # Write response body
                if self.scope["method"] == "HEAD":
                    body = b""
                else:
                    body = message.get("body", b"")
                self.conn.send_data(self.stream_id, body, end_stream=(not more_body))
                self.transport.write(self.conn.data_to_send())

                # Handle response completion
                if not more_body:
                    self.response_complete = True
            elif message_type == "http.response.push":
                push_stream_id = self.conn.get_next_available_stream_id()
                self.logger.debug("headers in scope %s", self.scope["headers"])
                request_headers = [
                    (ensure_bytes(name), ensure_bytes(value))
                    for name, value in (
                        (b":method", b"GET"),
                        (b":path", message["path"]),
                        (b":scheme", self.scope["scheme"]),
                        (b":authority", self.scope["authority"]),
                        *message["headers"],
                    )
                ]
                try:
                    self.conn.push_stream(
                        stream_id=self.stream_id,
                        promised_stream_id=push_stream_id,
                        request_headers=request_headers,
                    )
                except h2.exceptions.ProtocolError:
                    self.logger.debug("h2 protocol error.", exc_info=True)
                else:
                    event = h2.events.RequestReceived()
                    event.stream_id = push_stream_id
                    event.headers = request_headers
                    self.on_request(event)
                    self.transport.write(self.conn.data_to_send())
            else:
                msg = "Expected ASGI message 'http.response.body', but got '%s'."
                raise RuntimeError(msg % message_type)

        else:
            # Response already sent
            msg = "Unexpected ASGI message '%s' sent, after response already completed."
            raise RuntimeError(msg % message_type)

        if self.response_complete:
            self.on_response()

    async def receive(self):
        self.flow.resume_reading()
        await self.message_event.wait()
        self.message_event.clear()

        if self.disconnected or self.response_complete:
            message = {"type": "http.disconnect"}
        else:
            message = {
                "type": "http.request",
                "body": self.body,
                "more_body": self.more_body,
            }
            self.body = b""

        return message


def ensure_bytes(bytes_or_str):
    if isinstance(bytes_or_str, bytes):
        return bytes_or_str
    if isinstance(bytes_or_str, str):
        return bytes_or_str.encode("ascii")
    return bytes(bytes_or_str)
