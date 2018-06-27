import asyncio
import http
import logging
import traceback
from urllib.parse import unquote

import h11


logger = logging.getLogger()


def _get_status_phrase(status_code):
    try:
        return http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        return b''


STATUS_PHRASES = {
    status_code: _get_status_phrase(status_code) for status_code in range(100, 600)
}


class H11Protocol(asyncio.Protocol):
    def __init__(self, app, loop):
        self.app = app
        self.loop = loop
        self.conn = h11.Connection(h11.SERVER)

        # Per-connection state
        self.transport = None
        self.server = None
        self.client = None
        self.scheme = None

        # Per-request state
        self.scope = None
        self.queue = asyncio.Queue()

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
        logger.debug("%s - Connected", self.server[0])

    def connection_lost(self, exc):
        logger.debug("%s - Disconnected", self.server[0])
        message = {"type": "http.disconnect"}
        self.queue.put_nowait(message)
        event = h11.ConnectionClosed()
        self.conn.send(event)

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
                self.scope = {
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
                asgi = self.app(self.scope)
                self.loop.create_task(self.run_asgi(asgi))
                if self.conn.client_is_waiting_for_100_continue:
                    event = h11.InformationalResponse(status_code=100)
                    output = self.conn.send(event)
                    self.transport.write(output)
            elif event_type is h11.Data:
                if self.conn.our_state is h11.DONE:
                    continue
                self.pause_reading()
                message = {
                    "type": "http.request",
                    "body": event.data,
                    "more_body": True,
                }
                self.queue.put_nowait(message)
            elif event_type is h11.EndOfMessage:
                if self.conn.our_state is h11.DONE:
                    while not self.queue.empty():
                        self.queue.get_nowait()
                    self.resume_reading()
                    self.conn.start_next_cycle()
                    continue
                message = {"type": "http.request", "body": b"", "more_body": False}
                self.queue.put_nowait(message)

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

    # ASGI exception wrapper
    async def run_asgi(self, asgi):
        try:
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            logger.error(msg, traceback_text)
            if self.conn.our_state == h11.SEND_RESPONSE:
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
            elif self.conn.our_state == h11.SEND_BODY:
                event = h11.ConnectionClosed()
                self.conn.send(event)
                self.transport.close()
            return

        if result is not None:
            msg = "ASGI callable should return None, but returned '%s'."
            logger.error(msg, result)

    # ASGI interface
    async def send(self, message):
        if not self.writable:
            await self.writable_event.wait()

        message_type = message["type"]

        if message_type == "http.response.start":
            if self.conn.our_state != h11.SEND_RESPONSE:
                msg = "Unexpected ASGI message '%s' sent while in '%s' state."
                raise RuntimeError(msg % (message_type, self.conn.our_state))
            status_code = message["status"]
            headers = message.get("headers", [])
            logger.info(
                '%s - "%s %s HTTP/%s" %d',
                self.server[0],
                self.scope["method"],
                self.scope["path"],
                self.scope["http_version"],
                status_code,
            )
            reason = STATUS_PHRASES[status_code]
            event = h11.Response(status_code=status_code, headers=headers, reason=reason)
            output = self.conn.send(event)
            self.transport.write(output)
        elif message_type == "http.response.body":
            if self.conn.our_state != h11.SEND_BODY:
                msg = "Unexpected ASGI message '%s' sent while in '%s' state."
                raise RuntimeError(msg % message_type)
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            event = h11.Data(data=body)
            output = self.conn.send(event)
            if not more_body:
                event = h11.EndOfMessage()
                output += self.conn.send(event)
            self.transport.write(output)
        else:
            msg = "Unexpected ASGI message '%s' sent while in '%s' state."
            raise RuntimeError(msg % (message_type, self.conn.our_state))

        if self.conn.our_state is h11.MUST_CLOSE:
            event = h11.ConnectionClosed()
            self.conn.send(event)
            self.transport.close()
        elif self.conn.our_state is h11.DONE and self.conn.their_state is h11.DONE:
            while not self.queue.empty():
                self.queue.get_nowait()
            self.resume_reading()
            self.conn.start_next_cycle()

    async def receive(self):
        if self.conn.our_state == h11.CLOSED and self.queue.empty():
            raise RuntimeError("Connection is closed")

        self.resume_reading()
        return await self.queue.get()
