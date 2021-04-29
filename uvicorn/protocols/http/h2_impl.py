import asyncio
import collections
import http
import logging
from urllib.parse import unquote

import h2.config
import h2.connection
import h2.errors
import h2.events
import h2.exceptions

from uvicorn.protocols.utils import (
    get_local_addr,
    get_remote_addr,
    is_ssl,
)


def _get_status_phrase(status_code):
    try:
        return http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        return b""


STATUS_PHRASES = {
    status_code: _get_status_phrase(status_code) for status_code in range(100, 600)
}

CLOSE_HEADER = (b"connection", b"close")

HIGH_WATER_LIMIT = 65536

TRACE_LOG_LEVEL = 5


_StreamRequest = collections.namedtuple("_StreamRequest", ("headers", "scope", "cycle"))


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


async def service_unavailable(scope, receive, send):
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
    def __init__(self, config, server_state, _loop=None):
        if not config.loaded:
            config.load()

        self.config = config
        self.app = config.loaded_app
        self.loop = _loop or asyncio.get_event_loop()
        self.logger = logging.getLogger("uvicorn.error")
        self.access_logger = logging.getLogger("uvicorn.access")
        self.access_log = self.access_logger.hasHandlers()
        self.conn = h2.connection.H2Connection(
            config=h2.config.H2Configuration(client_side=False, header_encoding=None)
        )
        self.ws_protocol_class = config.ws_protocol_class
        self.root_path = config.root_path
        self.limit_concurrency = config.limit_concurrency

        # Timeouts
        self.timeout_keep_alive_task = None
        self.timeout_keep_alive = config.timeout_keep_alive

        # Shared server state
        self.server_state = server_state
        self.connections = server_state.connections
        self.tasks = server_state.tasks
        self.default_headers = server_state.default_headers

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

    # Protocol interface
    def connection_made(self, transport):
        self.connections.add(self)

        self.transport = transport
        self.flow = FlowControl(transport)
        self.server = get_local_addr(transport)
        self.client = get_remote_addr(transport)
        self.scheme = "https" if is_ssl(transport) else "http"

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.client) if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sConnection made", prefix)

        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def _unset_keepalive_if_required(self):
        if self.timeout_keep_alive_task is not None:
            self.timeout_keep_alive_task.cancel()
            self.timeout_keep_alive_task = None

    def data_received(self, data):
        self._unset_keepalive_if_required()
        try:
            events = self.conn.receive_data(data)
        except h2.exceptions.ProtocolError:
            self.transport.write(self.conn.data_to_send())
            self.transport.close()
        else:
            self.transport.write(self.conn.data_to_send())
            self.handle_events(events)

    def handle_events(self, events):
        for event in events:
            event_type = type(event)
            if event_type is h2.events.RequestReceived:
                self.on_request_received(event)
            elif event_type is h2.events.DataReceived:
                pass
            elif event_type is h2.events.StreamEnded:
                pass
            elif event_type is h2.events.StreamReset:
                pass
            elif event_type is h2.events.WindowUpdated:
                pass
            elif event_type is h2.events.PriorityUpdated:
                pass
            elif event_type is h2.events.RemoteSettingsChanged:
                pass
            elif event_type is h2.events.ConnectionTerminated:
                pass

    def on_request_received(self, event):
        raw_path, _, query_string = event.raw_path.partition(b"?")
        self.scope = {
            "type": "http",
            "asgi": {
                "version": self.config.asgi_version,
                "spec_version": "2.1",
            },
            "http_version": event.http_version.decode("ascii"),
            "server": self.server,
            "client": self.client,
            "root_path": self.root_path,
            "raw_path": raw_path,
            "path": unquote(raw_path),
            "query_string": query_string,
            'extensions': {"http.response.push": {}},
            'headers': [],
        }
        scope_mapping = {
            b":scheme": "scheme",
            b":authority": "authority",
            b":method": "method",
            b":path": "path",
        }
        for key, value in event.headers:
            if key in scope_mapping:
                self.scope[scope_mapping[key]] = value.decode("ascii")
            else:
                self.scope["headers"].append((key.lower(), value))

        # Handle 503 responses when 'limit_concurrency' is exceeded.
        if self.limit_concurrency is not None and (
                len(self.connections) >= self.limit_concurrency
                or len(self.tasks) >= self.limit_concurrency
        ):
            app = service_unavailable
            message = "Exceeded concurrency limit."
            self.logger.warning(message)
        else:
            app = self.app

        stream_id = event.stream_id

        cycle = RequestResponseCycle(
            stream_id=stream_id,
            scope=self.scope,
            conn=self.conn,
            transport=self.transport,
            flow=self.flow,
            logger=self.logger,
            access_logger=self.access_logger,
            access_log=self.access_log,
            default_headers=self.default_headers,
            message_event=asyncio.Event(),
            on_response=self.on_response_complete,
        )
        self.streams[stream_id] = _StreamRequest(
            headers=self.scope["headers"], scope=self.scope, cycle=cycle
        )
        self.logger.debug(
            "New request received, current stream(%s), all streams: %s",
            stream_id,
            list(self.streams.keys()),
        )
        task = self.loop.create_task(self.streams[stream_id].cycle.run_asgi(app))
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(
            lambda t: self.logger.debug(
                "stream(%s) done, path(%s)", stream_id, self.scope["path"]
            )
        )
        self.tasks.add(task)


    def on_response_complete(self):
        self.server_state.total_requests += 1

        if self.transport.is_closing():
            return

        # Set a short Keep-Alive timeout.
        self._unset_keepalive_if_required()

        self.timeout_keep_alive_task = self.loop.call_later(
            self.timeout_keep_alive, self.timeout_keep_alive_handler
        )

        # Unpause data reads if needed.
        self.flow.resume_reading()

        # Unblock any pipelined events.
        # if self.conn.our_state is h11.DONE and self.conn.their_state is h11.DONE:
        #     self.conn.start_next_cycle()
        #     self.handle_events()

    def timeout_keep_alive_handler(self):
        """
        Called on a keep-alive connection if no new data is received after a short delay.
        """
        if not self.transport.is_closing():
            for stream_id, stream in self.streams.items():
                self.conn.close_connection(last_stream_id=stream_id)
                self.transport.write(self.conn.data_to_send())
            self.transport.close()


class RequestResponseCycle:
    def __init__(
            self,
            stream_id,
            scope,
            conn,
            transport,
            flow,
            logger,
            access_logger,
            access_log,
            default_headers,
            message_event,
            on_response,
    ):
        self.stream_id = stream_id
        self.scope = scope
        self.conn = conn
        self.transport = transport
        self.flow = flow
        self.logger = logger
        self.access_logger = access_logger
        self.access_log = access_log
        self.default_headers = default_headers
        self.message_event = message_event
        self.on_response = on_response

        # Connection state
        self.disconnected = False
        self.keep_alive = True

        # Request state
        self.body = b""
        self.more_body = True

        # Response state
        self.response_started = False
        self.response_complete = False

