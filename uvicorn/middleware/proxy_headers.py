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

    def __init__(
        self,
        trusted_hosts: Union[List[str], str],
        trust_all_literal_clients: bool = False,
    ) -> None:
        self.always_trust: bool = trusted_hosts == "*"
        self.trust_all_literal_clients = trust_all_literal_clients

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
            if self.trust_all_literal_clients:
                return True
            return item in self.trusted_literals

    def get_trusted_client_host(self, x_forwarded_for: str) -> Optional[str]:
        """Extract the client host from x_forwarded_for header

        In general this is the first "untrusted" host in the forwarded for list.
        """
        x_forwarded_for_hosts = _parse_raw_hosts(x_forwarded_for)

        if not x_forwarded_for_hosts:
            return None

        if self.always_trust:
            return x_forwarded_for_hosts[0]

        # Note: each proxy appends to the header list so check it in reverse order
        for host in reversed(x_forwarded_for_hosts):
            if host not in self:
                return host

        # All hosts are trusted meaning that the client was also a trusted proxy
        # See https://github.com/encode/uvicorn/issues/1068#issuecomment-855371576
        return x_forwarded_for_hosts[0]

    def __str__(self) -> str:
        if self.always_trust:
            return f"{self.__class__.__name__}(always_trust=True)"

        return (
            f"{self.__class__.__name__}({self.trusted_hosts=}, "
            f"{self.trusted_networks=}, {self.trusted_literals=}, "
            f"{self.trust_all_literal_clients=}"
        )


class ProxyHeadersMiddleware:
    """Middleware for handling known proxy headers

    This middleware can be used when a known proxy is fronting the application,
    and is trusted to be properly setting the `X-Forwarded-Proto` and
    `X-Forwarded-For` headers with the connecting client information.

    Modifies the `client` and `scheme` information so that they reference
    the connecting client, rather that the connecting proxy.

    Use `trust_none_client = True` to continue with proxy header handling when
    the initial client is `None`. This does not affect the handling of client
    adddresses in the proxy headers. If you are listening on a UNIX Domain Sockets
    you will need to set this to `True` to enable proxy handling.

    Use `trust_all_literal_clients = True` to trust all non-IP clients in the header.
    This is useful if you are using UNIX Domain Sockets to communicate between your
    proxies and do not wish to list each literal or if you do not know the value of
    each literal and startup.

    References:

    - <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#Proxies>
    - <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For>
    """

    def __init__(
        self,
        app: "ASGI3Application",
        trusted_hosts: Union[List[str], str] = "127.0.0.1",
        trust_none_client: bool = False,
        trust_all_literal_clients: bool = False,
    ) -> None:
        self.app = app
        self.trusted_hosts = _TrustedHosts(trusted_hosts, trust_all_literal_clients)
        self.trust_none_client = trust_none_client
        print(self.trusted_hosts)
        return

    async def __call__(
        self, scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
    ) -> None:
        if scope["type"] in ("http", "websocket"):
            scope = cast(Union[HTTPScope, WebSocketScope], scope)
            client_addr: Optional[Tuple[str, int]] = scope.get("client")

            if (client_addr is None and self.trust_none_client) or (
                client_addr is not None and client_addr[0] in self.trusted_hosts
            ):
                headers = dict(scope["headers"])

                # if b"forwarded" in headers:
                #     ...
                # https://github.com/encode/uvicorn/discussions/2236
                # TODO: We should probably also support the Forwarded header:
                # https://datatracker.ietf.org/doc/html/rfc7239
                # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Forwarded
                # If we do it should take precedence over the x-forwarded-* headers.

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
                    x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                    host = self.trusted_hosts.get_trusted_client_host(x_forwarded_for)

                    if host:
                        # If the x-forwarded-for header is empty then host is None or
                        # an empty string.
                        # Only set the client if we actually got something usable.
                        # See: https://github.com/encode/uvicorn/issues/1068

                        # Unless we can relaibly use x-forwarded-port (see below) then
                        # we will not have any port information so set it to 0.
                        port = 0
                        scope["client"] = (host, port)

                    # if b"x-forwarded-port" in headers:
                    #     ...
                    # https://github.com/encode/uvicorn/issues/1974
                    # TODO: Are we able to reliabily extract x-forwarded-port?
                    # https://docs.aws.amazon.com/elasticloadbalancing/latest/classic/x-forwarded-headers.html#x-forwarded-port
                    # If yes we should update the NGINX in docs/deployment.md

        return await self.app(scope, receive, send)
