import ipaddress
from typing import List, Optional, Set, Tuple, Union, cast

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
    """Container for trusted hosts and networks"""

    def __init__(self, trusted_hosts: Union[List[str], str]) -> None:
        self.always_trust: bool = trusted_hosts == "*"

        self.trusted_literals: Set[str] = set()
        self.trusted_hosts: Set[ipaddress._BaseAddress] = set()
        self.trusted_networks: Set[ipaddress._BaseNetwork] = set()

        # Notes:
        # - We seperate hosts from literals as there are many ways to write
        #   an IPv6 Address so we need to compare by object.
        # - We don't convert IP Address to single host networks (e.g. /32 / 128) as
        #   it more efficient to do an address lookup in a set than check for
        #   membership in each network.
        # - We still allow literals as it might be possible that we receive a
        #   something that isn't an IP Address e.g. a unix socket.

        if not self.always_trust:
            if isinstance(trusted_hosts, str):
                trusted_hosts = _parse_raw_hosts(trusted_hosts)

            for host in trusted_hosts:
                # Note: because we always convert invalid IP types to literals it
                # is not possible for the user to know they provided a malformed IP
                # type - this may lead to unexpected / difficult to debug behaviour.

                if "/" in host:
                    # Looks like a network
                    try:
                        self.trusted_networks.add(ipaddress.ip_network(host))
                    except ValueError:
                        # Was not a valid IP Network
                        self.trusted_literals.add(host)
                else:
                    try:
                        self.trusted_hosts.add(ipaddress.ip_address(host))
                    except ValueError:
                        # Was not a valid IP Adress
                        self.trusted_literals.add(host)
        return

    def __contains__(self, item: Optional[str]) -> bool:
        if self.always_trust:
            return True

        if not item:
            return False

        try:
            ip = ipaddress.ip_address(item)
            if ip in self.trusted_hosts:
                return True
            return any(ip in net for net in self.trusted_networks)

        except ValueError:
            return item in self.trusted_literals

    def get_trusted_client_host(self, x_forwarded_for: str) -> Optional[str]:
        """Extract the client host from x_forwarded_for header

        In general this is the first "untrusted" host in the forwarded for list.
        """
        x_forwarded_for_hosts = _parse_raw_hosts(x_forwarded_for)

        if self.always_trust:
            return x_forwarded_for_hosts[0]

        host: Optional[str] = None

        # Note: each proxy appends to the list so check it in reverse order
        for host in reversed(x_forwarded_for_hosts):
            if host not in self:
                return host

        # The request came from a client on the proxy itself. Trust it.
        # See https://github.com/encode/uvicorn/issues/1068#issuecomment-855371576
        if host in self:
            return x_forwarded_for_hosts[0]

        return host


class ProxyHeadersMiddleware:
    """Middleware for handling known proxy headers

    This middleware can be used when a known proxy is fronting the application,
    and is trusted to be properly setting the `X-Forwarded-Proto` and
    `X-Forwarded-For` headers with the connecting client information.

    Modifies the `client` and `scheme` information so that they reference
    the connecting client, rather that the connecting proxy.

    References:

    - <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#Proxies>
    - <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For>
    """

    # TODO: We should probably also support the Forwarded header:
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Forwarded

    def __init__(
        self,
        app: "ASGI3Application",
        trusted_hosts: Union[List[str], str] = "127.0.0.1",
    ) -> None:
        self.app = app
        self.trusted_hosts = _TrustedHosts(trusted_hosts)
        return

    async def __call__(
        self, scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
    ) -> None:
        if scope["type"] in ("http", "websocket"):
            scope = cast(Union[HTTPScope, WebSocketScope], scope)
            client_addr: Optional[Tuple[str, int]] = scope.get("client")

            if client_addr and client_addr[0] in self.trusted_hosts:
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

                    # Host is None or an empty string
                    # if the x-forwarded-for header is empty.
                    # See https://github.com/encode/uvicorn/issues/1068
                    if host:
                        port = 0
                        scope["client"] = (host, port)  # type: ignore[arg-type]

        return await self.app(scope, receive, send)
