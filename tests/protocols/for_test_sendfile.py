async def app(scope, receive, send):
    with open("./README.md", "rb") as file:
        content_length = len(file.read())
        file.seek(0, 0)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"Content-Length", str(content_length).encode("ascii")),
                    (b"Content-Type", b"text/plain; charset=utf8"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.zerocopysend",
                "file": file.fileno(),
            }
        )
