"""
This middleware can be used when a known proxy is fronting the application,
and is trusted to be properly setting the `X-Forwarded-Proto` and
`X-Forwarded-For` headers with the connecting client information.

Modifies the `client` and `scheme` information so that they reference
the connecting client, rather that the connecting proxy.

https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#Proxies
"""
from __future__ import annotations

import ipaddress
from typing import Union, cast

from uvicorn._types import ASGI3Application, ASGIReceiveCallable, ASGISendCallable, HTTPScope, Scope, WebSocketScope


class ProxyHeadersMiddleware:
    def __init__(
        self,
        app: ASGI3Application,
        trusted_hosts: list[str] | str = "127.0.0.1",
    ) -> None:
        self.app = app
        if isinstance(trusted_hosts, str):
            trusted_hosts_set = {item.strip() for item in trusted_hosts.split(",")}
        else:
            trusted_hosts_set = set(trusted_hosts)
        self.always_trust = "*" in trusted_hosts_set
        trusted_hosts_set.discard("*")

        self.trusted_hosts = {ipaddress.ip_network(host) for host in trusted_hosts_set}

    def get_trusted_client_host(self, x_forwarded_for_hosts: list[str]) -> str:
        if self.always_trust:
            return x_forwarded_for_hosts[0]

        for host in reversed(x_forwarded_for_hosts):
            if not self.check_trusted_host(host):
                return host

        return ""
        

    def check_trusted_host(self, host: str) -> bool:
        for trusted_net in self.trusted_hosts:
            if ipaddress.ip_address(host) in trusted_net:
                return True
        return False

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        if scope["type"] in ("http", "websocket"):
            scope = cast(Union["HTTPScope", "WebSocketScope"], scope)
            client_addr: tuple[str, int] | None = scope.get("client")
            client_host = client_addr[0] if client_addr else None

            if self.always_trust or self.check_trusted_host(client_host):
                headers = dict(scope["headers"])

                if b"x-forwarded-proto" in headers:
                    # Determine if the incoming request was http or https based on
                    # the X-Forwarded-Proto header.
                    x_forwarded_proto = headers[b"x-forwarded-proto"].decode("latin1").strip()
                    if scope["type"] == "websocket":
                        scope["scheme"] = x_forwarded_proto.replace("http", "ws")
                    else:
                        scope["scheme"] = x_forwarded_proto

                if b"x-forwarded-for" in headers:
                    # Determine the client address from the last trusted IP in the
                    # X-Forwarded-For header. We've lost the connecting client's port
                    # information by now, so only include the host.
                    x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                    x_forwarded_for_hosts = [item.strip() for item in x_forwarded_for.split(",")]
                    host = self.get_trusted_client_host(x_forwarded_for_hosts)
                    port = 0
                    scope["client"] = (host, port)

        return await self.app(scope, receive, send)
