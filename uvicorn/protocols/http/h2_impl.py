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
    get_client_addr,
    get_local_addr,
    get_path_with_query_string,
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
    def connection_made(self, transport, upgrade_request=None):
        self.connections.add(self)

        self.transport = transport
        self.flow = FlowControl(transport)
        self.server = get_local_addr(transport)
        self.client = get_remote_addr(transport)
        self.scheme = "https" if is_ssl(transport) else "http"

        if upgrade_request is None:
            self.conn.initiate_connection()
        else:
            # Different implementations for httptools and h11
            return

        self.transport.write(self.conn.data_to_send())
        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.client) if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sConnection made", prefix)

    def connection_lost(self, exc):
        self.connections.discard(self)

        self.logger.debug("%s - Disconnected", self.client[0])

        for stream_id, stream in self.streams.items():
            if stream.cycle:
                if not stream.cycle.response_complete:
                    stream.cycle.disconnected = True
                    try:
                        self.conn.close_connection(last_stream_id=stream_id)
                        self.transport.write(self.conn.data_to_send())
                    except h2.exceptions.ProtocolError as err:
                        self.logger.debug(
                            "connection lost, failed to close connection.", exc_info=err
                        )
                stream.cycle.message_event.set()

        self.logger.debug(
            "Disconnected, current streams: %s", list(self.streams.keys()), exc_info=exc
        )
        self.streams = {}
        if self.flow is not None:
            self.flow.resume_writing()

    def _unset_keepalive_if_required(self):
        if self.timeout_keep_alive_task is not None:
            self.timeout_keep_alive_task.cancel()
            self.timeout_keep_alive_task = None

    def eof_received(self):
        self.logger.debug(
            "eof received, current streams: %s", list(self.streams.keys())
        )
        self.streams = {}

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
                self.on_data_received(event)
            elif event_type is h2.events.StreamEnded:
                self.on_stream_ended(event)
            elif event_type is h2.events.StreamReset:
                self.on_stream_reset(event)
            elif event_type is h2.events.WindowUpdated:
                pass
            elif event_type is h2.events.PriorityUpdated:
                pass
            elif event_type is h2.events.RemoteSettingsChanged:
                pass
            elif event_type is h2.events.ConnectionTerminated:
                self.on_connection_terminated(event)
            self.transport.write(self.conn.data_to_send())

    def on_request_received(self, event: h2.events.RequestReceived):
        self.scope = {
            "type": "http",
            "asgi": {
                "version": self.config.asgi_version,
                "spec_version": "2.1",
            },
            "http_version": "2",
            "server": self.server,
            "client": self.client,
            "root_path": self.root_path,
            'extensions': {"http.response.push": {}},
            'headers': [],
        }
        scope_mapping = {
            b":scheme": "scheme",
            b":authority": "authority",
            b":method": "method",
            b":path": "raw_path",
        }
        for key, value in event.headers:
            if key in scope_mapping:
                self.scope[scope_mapping[key]] = value.decode("ascii")
            else:
                self.scope["headers"].append((key.lower(), value))
        path, _, query_string = self.scope["raw_path"].partition("?")
        self.scope["path"], self.scope["query_string"] = (
            unquote(path),
            query_string.encode("ascii"),
        )

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

    def on_data_received(self, event: h2.events.DataReceived):
        stream_id = event.stream_id
        self.logger.debug(
            "On data received, current %s, streams: %s", stream_id, self.streams.keys()
        )
        try:
            self.streams[stream_id].cycle.body += event.data
        except KeyError:
            self.conn.reset_stream(
                stream_id, error_code=h2.errors.ErrorCodes.PROTOCOL_ERROR
            )
        else:
            # In Hypercorn:
            # self.conn.acknowledge_received_data(
            #     event.flow_controlled_length, event.stream_id
            # )
            # To be done here, or in RequestResponseCycle's `receive()`? 😕
            body_size = len(self.streams[stream_id].cycle.body)
            if body_size > HIGH_WATER_LIMIT:
                self.flow.pause_reading()
            self.streams[stream_id].cycle.message_event.set()

    def on_stream_ended(self, event: h2.events.StreamEnded):
        stream_id = event.stream_id
        self.logger.debug(
            "On stream ended, current %s, streams: %s", stream_id, self.streams.keys()
        )
        try:
            stream = self.streams[stream_id]
        except KeyError:
            self.conn.reset_stream(
                stream_id, error_code=h2.errors.ErrorCodes.STREAM_CLOSED
            )
        else:
            self.flow.resume_reading()
            stream.cycle.more_body = False
            self.streams[stream_id].cycle.message_event.set()

    def on_stream_reset(self, event: h2.events.StreamReset):
        self.logger.debug(
            "stream(%s) reset by %s with error_code %s",
            event.stream_id,
            "server" if event.remote_reset else "remote peer",
            event.error_code,
        )
        self.streams.pop(event.stream_id, None)
        # In Hypercorn:
        # app_put({"type": "http.disconnect"})

    def on_connection_terminated(self, event: h2.events.ConnectionTerminated):
        stream_id = event.last_stream_id
        self.logger.debug(
            "H2Connection terminated, additional_data(%s), error_code(%s), last_stream(%s), streams: %s",
            event.additional_data,
            event.error_code,
            stream_id,
            list(self.streams.keys()),
        )
        stream = self.streams.pop(stream_id)
        if stream:
            stream.cycle.disconnected = True
        self.conn.close_connection(last_stream_id=stream_id)
        self.transport.write(self.conn.data_to_send())
        self.transport.close()

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

    def handle_upgrade(self, event):
        pass

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

    def shutdown(self):
        self.logger.debug(
            "Shutdown. streams: %s, tasks: %s", self.streams.keys(), self.tasks
        )
        for stream_id, stream in self.streams.items():
            if stream.cycle is None or stream.cycle.response_complete:
                self.conn.close_connection(last_stream_id=stream_id)
                self.transport.write(self.conn.data_to_send())
            else:
                stream.cycle.keep_alive = False
        self.streams = {}
        self.transport.close()

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

    # ASGI exception wrapper
    async def run_asgi(self, app):
        try:
            result = await app(self.scope, self.receive, self.send)
        except BaseException as exc:
            msg = "Exception in ASGI application\n"
            self.logger.error(msg, exc_info=exc)
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

            headers = self.default_headers + message.get("headers", [])

            if CLOSE_HEADER in self.scope["headers"] and CLOSE_HEADER not in headers:
                headers = headers + [CLOSE_HEADER]

            if self.access_log:
                self.access_logger.info(
                    '%s - "%s %s HTTP/%s" %d',
                    get_client_addr(self.scope),
                    self.scope["method"],
                    get_path_with_query_string(self.scope),
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
                pass
            else:
                msg = "Expected ASGI message 'http.response.body' or 'http.response.push', but got '%s'."
                raise RuntimeError(msg % message_type)
        else:
            # Response already sent
            msg = "Unexpected ASGI message '%s' sent, after response already completed."
            raise RuntimeError(msg % message_type)

        if self.response_complete:
            self.on_response()

    async def receive(self):
        if not self.disconnected and not self.response_complete:
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
