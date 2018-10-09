"""
This middleware can be used when a known proxy is fronting the application,
and is trusted to be properly setting the `X-Forwarded-Proto` and
`X-Forwarded-For` headers with the connecting client information.

Modifies the `client` and `scheme` information so that they reference
the connecting client, rather that the connecting proxy.

https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#Proxies
"""

class ProxyHeadersMiddleware:
    def __init__(self, app, num_proxies=1):
        self.app = app
        self.num_proxies = num_proxies

    def __call__(self, scope):
        if scope["type"] in ("http", "websocket"):
            headers = dict(scope["headers"])

            if b"x-forwarded-proto" in headers:
                # Determine if the incoming request was http or https based on
                # the X-Forwarded-Proto header.
                x_forwarded_proto = headers[b"x-forwarded-proto"].decode("ascii")
                scope["scheme"] = x_forwarded_proto.strip()

            if b"x-forwarded-for" in headers:
                # Determine the client address from the last trusted IP in the
                # X-Forwarded-For header. We've lost the connecting client's port
                # information by now, so only include the host.
                x_forwarded_for = headers[b"x-forwarded-for"].decode("ascii")
                host = x_forwarded_for.split(",")[-self.num_proxies].strip()
                port = 0
                scope["client"] = (host, port)

        return self.app(scope)
