# import asyncio
# import functools
# import threading
# import requests
# import pytest
# import websockets
# from contextlib import contextmanager
# from uvicorn.protocols import http
#
#
# def run_loop(loop):
#     loop.run_forever()
#     loop.close()
#
#
# @contextmanager
# def run_server(app):
#     asyncio.set_event_loop(None)
#     loop = asyncio.new_event_loop()
#     protocol = functools.partial(http.HttpProtocol, consumer=app, loop=loop)
#     create_server_task = loop.create_server(protocol, host='127.0.0.1')
#     server = loop.run_until_complete(create_server_task)
#     url = 'ws://127.0.0.1:%d/' % server.sockets[0].getsockname()[1]
#     try:
#         # Run the event loop in a new thread.
#         threading.Thread(target=run_loop, args=[loop]).start()
#         # Return the contextmanager state.
#         yield url
#     finally:
#         # Close the loop from our main thread.
#         loop.call_soon_threadsafe(loop.stop)
#
#
# def test_invalid_upgrade():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             message = await receive()
#             status = message['status']
#             await send({
#                 'type': 'http.response.start',
#                 'status': status,
#                 'headers': [(b'content-Type', b'text/html')],
#             })
#             await send({
#                 'type': 'http.response.body',
#                 'body': b'',
#                 'more_body': False,
#             })
#     with run_server(App) as url:
#         url = url.replace('ws://', 'http://')
#         response = requests.get(url, headers={'upgrade': 'websocket', 'connection': 'upgrade'}, timeout=5)
#         assert response.status_code == 403
#
#
# def test_accept_connection():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             message = await receive()
#             if message['type'] == 'websocket.connect':
#                 await send({'type': 'websocket.accept'})
#
#     async def open_connection(url):
#         async with websockets.connect(url) as websocket:
#             return websocket.open
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         is_open = loop.run_until_complete(open_connection(url))
#         assert is_open
#         loop.close()
#
#
# def test_send_text_data_to_client():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             message = await receive()
#             if message['type'] == 'websocket.connect':
#                 await send({'type': 'websocket.accept'})
#                 await send({'type': 'websocket.send', 'text': '123'})
#
#     async def get_data(url):
#         async with websockets.connect(url) as websocket:
#             return await websocket.recv()
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         data = loop.run_until_complete(get_data(url))
#         assert data == '123'
#         loop.close()
#
#
# def test_send_binary_data_to_client():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             message = await receive()
#             if message['type'] == 'websocket.connect':
#                 await send({'type': 'websocket.accept'})
#                 await send({'type': 'websocket.send', 'bytes': b'123'})
#
#     async def get_data(url):
#         async with websockets.connect(url) as websocket:
#             return await websocket.recv()
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         data = loop.run_until_complete(get_data(url))
#         assert data == b'123'
#         loop.close()
#
#
# def test_send_and_close_connection():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             message = await receive()
#             if message['type'] == 'websocket.connect':
#                 await send({'type': 'websocket.close', 'text': '123'})
#
#     async def get_data(url):
#         async with websockets.connect(url) as websocket:
#             data = await websocket.recv()
#             is_open = True
#             try:
#                 await websocket.recv()
#             except:
#                 is_open = False
#             return (data, is_open)
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         (data, is_open) = loop.run_until_complete(get_data(url))
#         assert data == '123'
#         assert not is_open
#         loop.close()
#
#
# def test_send_text_data_to_server():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             while True:
#                 message = await receive()
#                 if message['type'] == 'websocket.connect':
#                     await send({'type': 'websocket.accept'})
#                 if message['type'] == 'websocket.receive':
#                     data = message.get('text')
#                     await send({'type': 'websocket.send', 'text': data})
#                     return
#
#     async def send_text(url):
#         async with websockets.connect(url) as websocket:
#             await websocket.send('abc')
#             return await websocket.recv()
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         data = loop.run_until_complete(send_text(url))
#         assert data == 'abc'
#         loop.close()
#
#
# def test_send_binary_data_to_server():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             while True:
#                 message = await receive()
#                 if message['type'] == 'websocket.connect':
#                     await send({'type': 'websocket.accept'})
#                 if message['type'] == 'websocket.receive':
#                     data = message.get('bytes')
#                     await send({'type': 'websocket.send', 'bytes': data})
#                     return
#
#     async def send_text(url):
#         async with websockets.connect(url) as websocket:
#             await websocket.send(b'abc')
#             return await websocket.recv()
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         data = loop.run_until_complete(send_text(url))
#         assert data == b'abc'
#         loop.close()
#
#
# def test_send_after_protocol_close():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             message = await receive()
#             if message['type'] == 'websocket.connect':
#                 await send({'type': 'websocket.close', 'text': '123'})
#                 with pytest.raises(Exception):
#                     await send({'type': 'websocket.send', 'text': '1234'})
#
#     async def get_data(url):
#         async with websockets.connect(url) as websocket:
#             data = await websocket.recv()
#             is_open = True
#             try:
#                 await websocket.recv()
#             except:
#                 is_open = False
#             return (data, is_open)
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         (data, is_open) = loop.run_until_complete(get_data(url))
#         assert data == '123'
#         assert not is_open
#         loop.close()
#
#
# def test_subprotocols():
#     class App:
#         def __init__(self, scope):
#             self.scope = scope
#
#         async def __call__(self, receive, send):
#             message = await receive()
#             if message['type'] == 'websocket.connect':
#                 await send({'type': 'websocket.accept', 'subprotocol': 'proto1'})
#
#     async def get_subprotocol(url):
#         async with websockets.connect(url, subprotocols=['proto1', 'proto2']) as websocket:
#             return websocket.subprotocol
#
#     with run_server(App) as url:
#         loop = asyncio.new_event_loop()
#         subprotocol = loop.run_until_complete(get_subprotocol(url))
#         assert subprotocol == 'proto1'
#         loop.close()
