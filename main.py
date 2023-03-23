# Simple ASGI websocket application
import uvicorn


async def app(scope, receive, send):
    assert scope["type"] == "websocket"
    while True:
        event = await receive()
        if event["type"] == "websocket.connect":
            await send({"type": "websocket.accept"})
        elif event["type"] == "websocket.receive":
            await send({"type": "websocket.send", "text": event["text"]})
        elif event["type"] == "websocket.disconnect":
            break


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        ws="uvicorn.protocols.websockets.websockets_sansio_impl:WebSocketsSansIOProtocol",
    )
