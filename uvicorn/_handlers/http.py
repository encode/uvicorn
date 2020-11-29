import asyncio
from typing import TYPE_CHECKING

from uvicorn.config import Config

if TYPE_CHECKING:  # pragma: no cover
    from uvicorn.server import ServerState

MAX_RECV = 65536


async def handle_http(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    server_state: "ServerState",
    config: Config,
) -> None:
    # Run transport/protocol session from streams.
    # https://docs.python.org/3/library/asyncio-protocol.html#connecting-existing-sockets

    loop = asyncio.get_event_loop()
    connection_lost = loop.create_future()

    # Switch the protocol from the stream reader to our own HTTP protocol class.
    protocol = config.http_protocol_class(
        config=config,
        server_state=server_state,
        on_connection_lost=lambda: connection_lost.set_result(True),
    )
    transport = writer.transport
    transport.set_protocol(protocol)

    # Kick off the HTTP protocol.
    protocol.connection_made(transport)

    # Pass any data already in the read buffer.
    try:
        # timeout=0: we don't want to wait for the client to send data. We only want
        # to access and ingest any data readily available in memory.
        data = await asyncio.wait_for(reader.read(MAX_RECV), timeout=0)
    except asyncio.TimeoutError:
        # No data in the read buffer yet.
        pass
    else:
        protocol.data_received(data)

    # Let the transport run in the background. When closed, this future will complete
    # and we'll exit here. Any exception raised by the transport will bubble up here
    # as well.
    await connection_lost
