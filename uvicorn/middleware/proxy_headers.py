class ProxyHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, scope):
        headers = dict(scope["headers"])

        if b"x-forwarded-proto" in headers:
            scope["scheme"] = headers[b"x-forwarded-proto"].decode("ascii").strip()

        if b"x-forwarded-for" in headers:
            host = headers[b"x-forwarded-for"].decode("ascii").split(",")[-1].strip()
            try:
                port = int(headers[b"x-forwarded-port"].decode("ascii"))
            except (KeyError, ValueError):
                port = 0
            scope["client"] = (host, port)

        return self.app(scope)
