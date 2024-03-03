class Response:
    charset = "utf-8"

    def __init__(self, content, status_code=200, headers=None, media_type=None):
        self.body = self.render(content)
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type
        self.set_content_type()
        self.set_content_length()

    async def __call__(self, scope, receive, send) -> None:
        prefix = "websocket." if scope["type"] == "websocket" else ""
        await send(
            {
                "type": prefix + "http.response.start",
                "status": self.status_code,
                "headers": [[key.encode(), value.encode()] for key, value in self.headers.items()],
            }
        )
        await send({"type": prefix + "http.response.body", "body": self.body})

    def render(self, content) -> bytes:
        if isinstance(content, bytes):
            return content
        return content.encode(self.charset)

    def set_content_length(self):
        if "content-length" not in self.headers:
            self.headers["content-length"] = str(len(self.body))

    def set_content_type(self):
        if self.media_type is not None and "content-type" not in self.headers:
            content_type = self.media_type
            if content_type.startswith("text/") and self.charset is not None:
                content_type += "; charset=%s" % self.charset
            self.headers["content-type"] = content_type
