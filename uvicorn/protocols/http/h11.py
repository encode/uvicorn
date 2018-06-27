import asyncio
import http
import logging
import traceback
from urllib.parse import unquote

import h11


def _get_status_phrase(status_code):
    try:
        return http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        return b''


STATUS_PHRASES = {
    status_code: _get_status_phrase(status_code) for status_code in range(100, 600)
}


class H11Protocol(asyncio.Protocol):
    def __init__(self, app, loop=None, logger=None):
        self.app = app
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logger or logging.getLogger()
        self.access_logs = self.logger.level >= logging.INFO
        self.conn = h11.Connection(h11.SERVER)

        # Per-connection state
        self.transport = None
        self.server = None
        self.client = None
        self.scheme = None

        # Per-request state
        self.cycle = None
        self.client_event = asyncio.Event()

        # Flow control
        self.readable = True
        self.writable = True
        self.writable_event = asyncio.Event()
        self.writable_event.set()

    # Protocol interface
    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info("sockname")
        self.client = transport.get_extra_info("peername")
        self.scheme = "https" if transport.get_extra_info("sslcontext") else "http"
        if self.access_logs:
            self.logger.debug("%s - Connected", self.server[0])

    def connection_lost(self, exc):
        if self.access_logs:
            self.logger.debug("%s - Disconnected", self.server[0])

        if self.cycle and self.cycle.more_body:
            self.cycle.disconnected = True
        event = h11.ConnectionClosed()
        self.conn.send(event)
        self.client_event.set()

    def eof_received(self):
        pass

    def data_received(self, data):
        self.conn.receive_data(data)
        while True:
            event = self.conn.next_event()
            event_type = type(event)
            if event_type is h11.NEED_DATA:
                break
            elif event_type is h11.PAUSED:
                self.pause_reading()
                break
            elif event_type is h11.Request:
                path, _, query_string = event.target.partition(b"?")
                scope = {
                    "type": "http",
                    "http_version": event.http_version.decode("ascii"),
                    "server": self.server,
                    "client": self.client,
                    "scheme": self.scheme,
                    "method": event.method.decode("ascii"),
                    "path": unquote(path.decode("ascii")),
                    "query_string": query_string,
                    "headers": event.headers,
                }
                self.cycle = RequestResponseCycle(scope, self)
                asgi = self.app(scope)
                self.loop.create_task(self.cycle.run_asgi(asgi))
            elif event_type is h11.Data:
                self.cycle.body += event.data
                self.pause_reading()
                self.client_event.set()
            elif event_type is h11.EndOfMessage:
                if self.conn.our_state is h11.DONE:
                    self.resume_reading()
                    self.conn.start_next_cycle()
                    continue
                self.cycle.more_body = False
                self.pause_reading()
                self.client_event.set()

    # Flow control
    def pause_reading(self):
        if self.readable:
            self.readable = False
            self.transport.pause_reading()

    def resume_reading(self):
        if not self.readable:
            self.readable = True
            self.transport.resume_reading()

    def pause_writing(self):
        if self.writable:
            self.writable = False
            self.writable_event.clear()

    def resume_writing(self):
        if not self.writable:
            self.writable = True
            self.writable_event.set()


class RequestResponseCycle:
    def __init__(self, scope, protocol):
        self.scope = scope
        self.protocol = protocol
        self.body = b''
        self.more_body = True
        self.disconnected = False

    # ASGI exception wrapper
    async def run_asgi(self, asgi):
        try:
            result = await asgi(self.receive, self.send)
        except:
            protocol = self.protocol

            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            protocol.logger.error(msg, traceback_text)
            if protocol.conn.our_state == h11.SEND_RESPONSE:
                await self.send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"text/plain; charset=utf-8"),
                        (b"connection", b"close")
                    ]
                })
                await self.send({
                    "type": "http.response.body",
                    "body": b"Internal Server Error"
                })
            elif protocol.conn.our_state == h11.SEND_BODY:
                event = h11.ConnectionClosed()
                protocol.conn.send(event)
                protocol.transport.close()
            return

        if result is not None:
            msg = "ASGI callable should return None, but returned '%s'."
            protocol.logger.error(msg, result)

    # ASGI interface
    async def send(self, message):
        protocol = self.protocol
        message_type = message["type"]

        if not protocol.writable:
            await protocol.writable_event.wait()

        if message_type == "http.response.start":
            if protocol.conn.our_state != h11.SEND_RESPONSE:
                msg = "Unexpected ASGI message '%s' sent while in '%s' state."
                raise RuntimeError(msg % (message_type, self.conn.our_state))
            status_code = message["status"]
            headers = message.get("headers", [])
            if protocol.access_logs:
                protocol.logger.info(
                    '%s - "%s %s HTTP/%s" %d',
                    protocol.server[0],
                    self.scope["method"],
                    self.scope["path"],
                    self.scope["http_version"],
                    status_code,
                )
            reason = STATUS_PHRASES[status_code]
            event = h11.Response(status_code=status_code, headers=headers, reason=reason)
            output = protocol.conn.send(event)
            protocol.transport.write(output)
        elif message_type == "http.response.body":
            if protocol.conn.our_state != h11.SEND_BODY:
                msg = "Unexpected ASGI message '%s' sent while in '%s' state."
                raise RuntimeError(msg % message_type)
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            event = h11.Data(data=body)
            output = protocol.conn.send(event)
            if not more_body:
                event = h11.EndOfMessage()
                output += protocol.conn.send(event)
            protocol.transport.write(output)
        else:
            msg = "Unexpected ASGI message '%s' sent while in '%s' state."
            raise RuntimeError(msg % (message_type, self.conn.our_state))

        if protocol.conn.our_state is h11.MUST_CLOSE:
            event = h11.ConnectionClosed()
            protocol.conn.send(event)
            protocol.transport.close()
        elif protocol.conn.our_state is h11.DONE and protocol.conn.their_state is h11.DONE:
            protocol.resume_reading()
            protocol.conn.start_next_cycle()

    async def receive(self):
        protocol = self.protocol

        if self.more_body and not self.body and not self.disconnected:
            protocol.resume_reading()
            await protocol.client_event.wait()
            protocol.client_event.clear()

        if self.disconnected:
            message = {"type": "http.disconnect"}
        else:
            message = {
                "type": "http.request",
                "body": self.body,
                "more_body": self.more_body,
            }
            self.body = b''
            protocol.resume_reading()

        return message
