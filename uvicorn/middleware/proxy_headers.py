"""
This middleware can be used when a known proxy is fronting the application,
and is trusted to be properly setting the `X-Forwarded-Proto` and
`X-Forwarded-For` headers with the connecting client information.

Modifies the `client` and `scheme` information so that they reference
the connecting client, rather that the connecting proxy.

https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#Proxies
"""


class ProxyHeadersMiddleware:
    def __init__(self, app, trusted_hosts="127.0.0.1"):
        self.app = app
        if isinstance(trusted_hosts, str):
            self.trusted_hosts = [item.strip() for item in trusted_hosts.split(",")]
        else:
            self.trusted_hosts = trusted_hosts
        self.always_trust = "*" in self.trusted_hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            client_addr = scope.get("client")
            client_host = client_addr[0] if client_addr else None

            if self.always_trust or client_host in self.trusted_hosts:
                headers = dict(scope["headers"])

                if b"x-forwarded-proto" in headers:
                    # Determine if the incoming request was http or https based on
                    # the X-Forwarded-Proto header.
                    x_forwarded_proto = headers[b"x-forwarded-proto"].decode("latin1")
                    scope["scheme"] = x_forwarded_proto.strip()

                if b"x-forwarded-for" in headers:
                    # Determine the client address from the last trusted IP in the
                    # X-Forwarded-For header. We've lost the connecting client's port
                    # information by now, so only include the host.
                    x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                    host = x_forwarded_for.split(",")[-1].strip()
                    port = 0
                    scope["client"] = (host, port)

        return await self.app(scope, receive, send)
