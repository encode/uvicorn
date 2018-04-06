"""
Start a redis server:

$ redis-server

Start one or more uvicorn instances:

$ uvicorn app:chat_server --bind 127.0.0.1:8000
$ uvicorn app:chat_server --bind 127.0.0.1:8001
$ uvicorn app:chat_server --bind 127.0.0.1:8002
"""
with open('index.html', 'rb') as file:
    homepage = file.read()


class WebsocketApp:

    def __init__(self, scope):
        self.scope = scope
        print(self.scope)

    async def __call__(self, receive, send): 
        self.send = send
        message = await receive()
        if message['type'] == 'websocket.connect':
            await self.send({'type': 'websocket.accept'})
        elif message['type'] == 'websocket.receive':
            await self.send({'type': 'websocket.receive', 'text': 'test'})
        elif message['type'] == 'websocket.disconnect':
            print('Disconnect')
        elif message['type'] == 'http.request':
            await self.send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [(b'content-type', b'text/html')],
            })
            await self.send({
                'type': 'http.response.body',
                'body': homepage,
            })

wsapp = WebsocketApp