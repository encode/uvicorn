clients = {}

with open('index.html', 'rb') as file:
    homepage = file.read()


class App():

    def __init__(self, scope):
        self.scope = scope
        self.client_id = 'client:%s' % id(self)

    async def __call__(self, receive, send):
        message = await receive()
        self.send = send
        if message['type'] == 'websocket.connect':
            await send({'type': 'websocket.accept'})
            clients[self.client_id] = self
        elif message['type'] == 'websocket.receive':
            for client_id, client in clients.items():
                await client.send(message)
        elif message['type'] == 'websocket.disconnect':
            clients[self.client_id] = None
        elif message['type'] == 'http.request':
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    [b'content-type', b'text/html'],
                ],
            })
            await send({
                'type': 'http.response.body',
                'body': homepage,
            })
