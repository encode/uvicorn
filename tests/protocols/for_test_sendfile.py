from baize.asgi import FileResponse


class OnlySendfileFileResponse(FileResponse):
    def create_send_or_zerocopy(self, scope, send):
        async def sendfile(
            file_descriptor: int,
            offset: int = None,
            count: int = None,
            more_body: bool = False,
        ) -> None:
            message = {
                "type": "http.response.zerocopysend",
                "file": file_descriptor,
                "more_body": more_body,
            }
            if offset is not None:
                message["offset"] = offset
            if count is not None:
                message["count"] = count
            await send(message)

        return sendfile


async def app(scope, receive, send):
    response = FileResponse("./README.md")
    await response(scope, receive, send)
