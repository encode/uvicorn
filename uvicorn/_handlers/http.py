import asyncio

from uvicorn.config import Config
from uvicorn.server import ServerState

MAX_RECV = 65536


async def handle_http(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    server_state: ServerState,
    config: Config,
) -> None:
    # Run transport/protocol session from streams.
    # https://docs.python.org/3/library/asyncio-protocol.html#connecting-existing-sockets

    loop = asyncio.get_event_loop()
    connection_lost = loop.create_future()

    protocol = config.http_protocol_class(
        config=config,
        server_state=server_state,
        on_connection_lost=lambda: connection_lost.set_result(True),
    )
    transport = writer.transport
    transport.set_protocol(protocol)

    # Kick off the HTTP protocol, passing any data already in the read buffer.
    protocol.connection_made(transport)
    data = await reader.read(MAX_RECV)
    protocol.data_received(data)

    # Let the transport run in the background. When closed, the future will complete
    # and we'll exit here.
    await connection_lost
