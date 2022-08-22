"""
This middleware can be used when a known proxy is fronting the application,
and is trusted to be properly setting the `X-Forwarded-Proto` and
`X-Forwarded-For` headers with the connecting client information.

Modifies the `client` and `scheme` information so that they reference
the connecting client, rather that the connecting proxy.

https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#Proxies
"""
import ipaddress
from typing import List, Optional, Tuple, Union, Set, cast

from uvicorn._types import (
    ASGI3Application,
    ASGIReceiveCallable,
    ASGISendCallable,
    HTTPScope,
    Scope,
    WebSocketScope,
)


def _parse_raw_hosts(value: str) -> List[str]:
    return [item.strip() for item in value.split(",")]


class _TrustedHosts:
    def __init__(self, trusted_hosts: Union[List[str], str]) -> None:
        self.trusted_networks: Set[ipaddress.IPv4Network] = set()
        self.trusted_literals: Set[str] = set()

        self.always_trust = trusted_hosts == "*"

        if not self.always_trust:
            if isinstance(trusted_hosts, str):
                trusted_hosts = _parse_raw_hosts(trusted_hosts)
            for host in trusted_hosts:
                try:
                    self.trusted_networks.add(ipaddress.IPv4Network(host))
                except ValueError:
                    self.trusted_literals.add(host)

    def __contains__(self, item: str):
        if self.always_trust:
            return True

        try:
            ip = ipaddress.IPv4Address(item)
            return any(ip in net for net in self.trusted_networks)
        except ValueError:
            return item in self.trusted_literals

    def get_trusted_client_host(self, x_forwarded_for: str) -> Optional[str]:
        x_forwarded_for_hosts = _parse_raw_hosts(x_forwarded_for)
        if self.always_trust:
            return x_forwarded_for_hosts[0]

        host = None
        for host in reversed(x_forwarded_for_hosts):
            if host not in self:
                return host
        # The request came from a client on the proxy itself. Trust it.
        if host in self:
            return x_forwarded_for_hosts[0]


class ProxyHeadersMiddleware:
    def __init__(
        self,
        app: "ASGI3Application",
        trusted_hosts: Union[List[str], str] = "127.0.0.1",
    ) -> None:
        self.app = app
        self.trusted_hosts = _TrustedHosts(trusted_hosts)

    async def __call__(
        self, scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
    ) -> None:
        if scope["type"] in ("http", "websocket"):
            scope = cast(Union["HTTPScope", "WebSocketScope"], scope)
            client_addr: Optional[Tuple[str, int]] = scope.get("client")
            client_host = client_addr[0] if client_addr else None

            if client_host in self.trusted_hosts:
                headers = dict(scope["headers"])

                if b"x-forwarded-proto" in headers:
                    # Determine if the incoming request was http or https based on
                    # the X-Forwarded-Proto header.
                    x_forwarded_proto = (
                        headers[b"x-forwarded-proto"].decode("latin1").strip()
                    )
                    if scope["type"] == "websocket":
                        scope["scheme"] = (
                            "wss" if x_forwarded_proto == "https" else "ws"
                        )
                    else:
                        scope["scheme"] = x_forwarded_proto

                if b"x-forwarded-for" in headers:
                    # Determine the client address from the last trusted IP in the
                    # X-Forwarded-For header. We've lost the connecting client's port
                    # information by now, so only include the host.
                    x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                    host = self.trusted_hosts.get_trusted_client_host(x_forwarded_for)
                    port = 0
                    scope["client"] = (host, port)  # type: ignore[arg-type]

        return await self.app(scope, receive, send)
