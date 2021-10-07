import asyncio
import os

try:
    os.sendfile
    HAS_SENDFILE = True
except AttributeError:
    HAS_SENDFILE = False

    async def sendfile(socket_fd: int, file_fd: int, offset: int, count: int) -> None:
        raise NotImplementedError


else:
    # Note: because uvloop don't implements loop.sendfile, so use os.sendfile as here
    # Related link: https://github.com/MagicStack/uvloop/issues/228
    async def sendfile(socket_fd: int, file_fd: int, offset: int, count: int) -> None:
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def call_sendfile(
            socket_fd: int, file_fd: int, offset: int, count: int, registered: bool
        ) -> None:
            if registered:
                loop.remove_writer(socket_fd)
            try:
                sent_count = os.sendfile(socket_fd, file_fd, offset, count)
            except BaseException as exc:
                future.set_exception(exc)
            else:
                if count - sent_count > 0:
                    new_offset = offset + sent_count
                    new_count = count - sent_count
                    loop.add_writer(
                        socket_fd,
                        call_sendfile,
                        socket_fd,
                        file_fd,
                        new_offset,
                        new_count,
                        True,
                    )
                else:
                    future.set_result(None)

        call_sendfile(socket_fd, file_fd, offset, count, False)
        return await future
