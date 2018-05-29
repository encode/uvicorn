class App:
    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/event-stream'],
            ]
        })
        n = 4
        for i in range(n + 1):
            body = 'Hi %s. ' % i
            body = body * 9999
            await send({
                'type': 'http.response.body',
                'body': body.encode(),
                'more_body': bool(i != n)
            })
# Run with uvicorn app:App --certfile=cert.crt --keyfile=cert.key
