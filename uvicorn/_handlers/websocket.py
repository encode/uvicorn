import asyncio

from .concurrency import AsyncioSocket
from .utils import WebSocketUpgrade
from uvicorn.config import Config
from uvicorn.server import ServerState


async def handle_websocket(
    sock: AsyncioSocket,
    server_state: ServerState,
    config: Config,
    upgrade: WebSocketUpgrade,
) -> None:
    # Run transport/protocol session from socket stream.
    # https://docs.python.org/3/library/asyncio-protocol.html#connecting-existing-sockets

    loop = asyncio.get_event_loop()

    # Should be set by the protocol when `.connection_lost()` is called.
    on_connection_lost = loop.create_future()

    # Switch protocols.
    protocol = config.ws_protocol_class(
        config=config,
        server_state=server_state,
        on_connection_lost=on_connection_lost,
    )
    transport = sock._stream_writer.transport
    protocol.connection_made(transport)
    transport.set_protocol(protocol)

    protocol.data_received(upgrade.initial_handshake_data())

    await on_connection_lost
