import asyncio


async def app(scope, receive, send):
    assert scope["type"] == "websocket"
    event = await receive()
    if event["type"] == "websocket.connect":
        await asyncio.sleep(10)
        await send({"type": "websocket.accept"})