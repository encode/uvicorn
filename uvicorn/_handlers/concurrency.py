import asyncio
from typing import Optional, Tuple

from .utils import get_sock_local_addr, get_sock_remote_addr


class AsyncioSocket:
    """
    Async socket interface.

    Aims at abstracting away any asyncio-specific interfaces.
    """

    def __init__(
        self, stream_reader: asyncio.StreamReader, stream_writer: asyncio.StreamWriter
    ) -> None:
        self._stream_reader = stream_reader
        self._stream_writer = stream_writer

    def get_local_addr(self) -> Optional[Tuple[str, int]]:
        sock = self._stream_writer.get_extra_info("socket")
        if sock is not None:
            return get_sock_local_addr(sock)

        info = self._stream_writer.get_extra_info("peername")
        try:
            host, port = info
        except ValueError:
            return None
        else:
            return str(host), int(port)

    def get_remote_addr(self) -> Optional[Tuple[str, int]]:
        sock = self._stream_writer.get_extra_info("socket")
        if sock is not None:
            return get_sock_remote_addr(sock)

        info = self._stream_writer.get_extra_info("peername")
        try:
            host, port = info
        except ValueError:
            return None
        else:
            return str(host), int(port)

    @property
    def is_ssl(self) -> bool:
        transport = self._stream_writer.transport
        return bool(transport.get_extra_info("sslcontext"))

    async def read(self, n: int) -> bytes:
        return await self._stream_reader.read(n)

    async def write(self, data: bytes) -> None:
        self._stream_writer.write(data)
        await self._stream_writer.drain()

    def send_eof(self) -> None:
        try:
            self._stream_writer.write_eof()
        except (NotImplementedError, OSError, RuntimeError):
            pass  # Likely SSL connection

    async def aclose(self) -> None:
        try:
            self._stream_writer.close()
            await self._stream_writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Already closed

    @property
    def is_closed(self) -> bool:
        return self._stream_writer.is_closing()
