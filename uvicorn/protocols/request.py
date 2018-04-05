import asyncio

import websockets

from uvicorn.protocols.response import HTTP_STATUS_LINES


class AsgiHttpRequestHandler:

    __slots__ = [
        'protocol',
        'transport',
        'response',
        'application_queue',
        'loop',
        'status',
        'has_started',
        'use_chunked_encoding',
        'seen_content_length',
        'should_keep_alive',
        'request_queue',
        'is_streaming',
    ]

    def __init__(self, protocol, transport, application_queue, loop=None):
        self.protocol = protocol
        self.response = None
        self.transport = transport
        self.application_queue = application_queue
        self.loop = loop or asyncio.get_event_loop()
        self.status = None
        self.has_started = False
        self.use_chunked_encoding = False
        self.seen_content_length = False
        self.should_keep_alive = True
        self.request_queue = None
        self.is_streaming = False

    async def __call__(self, message):
        try:
            message_type = message['type']
        except KeyError:
            raise ValueError('No message type specified')
        if message_type == 'http.response.start':
            if self.has_started:
                raise ValueError('Response already started')
            status = message.get('status')
            if not status:
                raise ValueError('No status provided')
            status = message['status']
            headers = message['headers']
            self.response = [
                HTTP_STATUS_LINES[status],
                b'Server: uvicorn\r\n'
            ]
            for header_name, header_value in headers:
                if header_name.lower() == b'content-length':
                    self.seen_content_length = True
                elif header_name.lower() == b'connection':
                    if header_value.lower() == b'close':
                        self.should_keep_alive = False
                self.response.append(b''.join([header_name, b': ', header_value, b'\r\n']))
            self.has_started = True
        elif message_type == 'http.response.body':
            if not self.has_started:
                raise ValueError('Response has not started, but type is http.response.body')
            else:
                body = message.get('body')
                more_body = message.get('more_body')
                if not self.seen_content_length:
                    if more_body:
                        self.use_chunked_encoding = True
                        self.response.append(b'transfer-encoding: chunked\r\n')
                    else:
                        self.response.append(b''.join([b'content-length: ', str(len(body)).encode(), b'\r\n']))
                self.response.append(b'\r\n')
                if self.is_streaming:
                    self.request_queue.put_nowait((body, more_body))
                else:
                    if self.use_chunked_encoding:
                        self.request_queue = asyncio.Queue()
                        self.loop.create_task(self.stream_writer())
                        self.is_streaming = True
                    else:
                        self.transport.write(b''.join(self.response))
                        if body:
                            self.transport.write(body)
                        if not more_body:
                            if self.use_chunked_encoding:
                                self.use_chunked_encoding = False
                            if not self.should_keep_alive or not self.protocol.request_parser.should_keep_alive():
                                self.transport.close()
                                self.protocol.transport = None
                            else:
                                self.protocol.request_handler = None
                            self.protocol.state['total_requests'] += 1
        else:
            raise ValueError('Unhandled response type: %s' % message_type)

    async def stream_listener(self):
        while True:
            body, more_body = await self.request_queue.get()
            self.transport.write(b'%x\r\n%b\r\n' % (len(body), body))
            if not more_body:
                break

    async def stream_writer(self):
        self.transport.write(b''.join(self.response))
        await self.stream_listener()
        self.transport.write(b'0\r\n\r\n')


class AsgiWebsocketRequestHandler:

    __slots__ = [
        'protocol',
        'application_queue',
        'loop',
    ]

    def __init__(self, protocol, application_queue):
        self.protocol = protocol
        self.application_queue = application_queue
        self.loop = protocol.loop

    async def reader(self):
        close_code = None
        path = self.protocol.message['path']
        try:
            async for data in self.protocol:
                await self.prepare_message(data, path)
        except websockets.exceptions.ConnectionClosed as exc:
            close_code = exc.code
            message = {
                'type': 'websocket.disconnect',
                'code': close_code,
                'path': path,
            }
            await self(message)

    async def __call__(self, message):
        # todo: Improve handling
        message_type = message.get('type')
        accept = bool(message_type == 'websocket.accept')
        text_data = message.get('text')
        bytes_data = message.get('bytes')
        close = message.get('close')
        if not self.protocol.accepted:
            if (accept is True) or (accept is None and (text_data or bytes_data)):
                self.protocol.accept()
                if not close:
                    asyncio.ensure_future(self.reader(), loop=self.loop)
            elif accept is False:
                text_data = None
                bytes_data = None
                close = True
        if text_data:
            await self.protocol.send(text_data)
        elif bytes_data:
            await self.protocol.send(bytes_data)
        if close:
            if not self.protocol.accepted:
                self.protocol.reject()
            else:
                code = 1000 if (close is True) else close
                await self.protocol.close(code=code)

    async def prepare_message(self, data, path):
        message = {
            'type': 'websocket.receive',
            'path': path
        }
        message['text'] = data if isinstance(data, str) else None
        message['bytes'] = data if isinstance(data, bytes) else None
        await self(message)
