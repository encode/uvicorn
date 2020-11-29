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
    """
    Handle an HTTP request connection.
    """

    # Run transport/protocol session from streams.
    # https://docs.python.org/3/library/asyncio-protocol.html#connecting-existing-sockets

    loop = asyncio.get_event_loop()

    # Should be set by the protocol when `.connection_lost()` is called.
    connection_lost = loop.create_future()

    def on_connection_lost() -> None:
        connection_lost.set_result(True)

    # Read any initial data already in the read buffer.
    # If we don't do this, any data already fed to the reader (such as request headers)
    # would never be passed to our protocol.
    data = await reader.read(MAX_RECV)

    # Switch from StreamReaderProtocol to our own HTTP protocol.
    protocol = config.http_protocol_class(
        config=config,
        server_state=server_state,
        on_connection_lost=on_connection_lost,
    )
    transport = writer.transport
    protocol.connection_made(transport)
    protocol.data_received(data)
    transport.set_protocol(protocol)

    try:
        # Let the transport run until the client disconnects.
        await connection_lost
    finally:
        transport.close()
