from __future__ import annotations

import ipaddress

from uvicorn._types import ASGI3Application, ASGIReceiveCallable, ASGISendCallable, Scope


class ProxyHeadersMiddleware:
    """Middleware for handling known proxy headers

    This middleware can be used when a known proxy is fronting the application,
    and is trusted to be properly setting the `X-Forwarded-Proto` and
    `X-Forwarded-For` headers with the connecting client information.

    Modifies the `client` and `scheme` information so that they reference
    the connecting client, rather that the connecting proxy.

    You can pass through a list of trusted hosts via the `trusted_hosts`
    parameter, which can be either a list or single entry. Each entry can be
    either a host ("127.0.0.1") or a network ("192.168.0.0/24"). An entry of
    "*" means that all hosts are trusted.

    Alternatively, if you know how many proxies are in front of your application
    you can pass the `trust_number_of_proxies` parameter to only trust the first
    N proxies. In this case you probably want to pass an empty list for
    `trusted_hosts`.

    References:
    - <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#Proxies>
    - <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For>
    """

    def __init__(
        self, app: ASGI3Application, trusted_hosts: list[str] | str = "127.0.0.1", trust_number_of_proxies: int = 0
    ) -> None:
        self.app = app
        self.trust_number_of_proxies = trust_number_of_proxies
        self.trusted_hosts = _TrustedHosts(trusted_hosts, trust_number_of_proxies)

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        client_addr = scope.get("client")
        client_host = client_addr[0] if client_addr else None

        if self.trust_number_of_proxies > 0 or client_host in self.trusted_hosts:
            headers = dict(scope["headers"])

            if b"x-forwarded-proto" in headers:
                x_forwarded_proto = headers[b"x-forwarded-proto"].decode("latin1").strip()

                if x_forwarded_proto in {"http", "https", "ws", "wss"}:
                    if scope["type"] == "websocket":
                        scope["scheme"] = x_forwarded_proto.replace("http", "ws")
                    else:
                        scope["scheme"] = x_forwarded_proto

            if b"x-forwarded-for" in headers:
                x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                host = self.trusted_hosts.get_trusted_client_host(x_forwarded_for)

                if host:
                    # If the x-forwarded-for header is empty then host is an empty string.
                    # Only set the client if we actually got something usable.
                    # See: https://github.com/encode/uvicorn/issues/1068

                    # We've lost the connecting client's port information by now,
                    # so only include the host.
                    port = 0
                    scope["client"] = (host, port)

        return await self.app(scope, receive, send)


def _parse_raw_hosts(value: str) -> list[str]:
    return [item.strip() for item in value.split(",")]


class _TrustedHosts:
    """Container for trusted hosts and networks"""

    def __init__(self, trusted_hosts: list[str] | str, trust_number_of_proxies: int = 0) -> None:
        self.always_trust: bool = trusted_hosts in ("*", ["*"])

        self.trusted_literals: set[str] = set()
        self.trusted_hosts: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        self.trusted_networks: set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()

        # Always trust the first N proxies, only apply the other arguments after
        # bypassing these.
        self.trust_number_of_proxies: int = trust_number_of_proxies

        # Notes:
        # - We separate hosts from literals as there are many ways to write
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
                        # Was not a valid IP Address
                        self.trusted_literals.add(host)

    def __contains__(self, host: str | None) -> bool:
        if self.always_trust:
            return True

        if not host:
            return False

        try:
            ip = ipaddress.ip_address(host)
            if ip in self.trusted_hosts:
                return True
            return any(ip in net for net in self.trusted_networks)

        except ValueError:
            return host in self.trusted_literals

    def get_trusted_client_host(self, x_forwarded_for: str) -> str:
        """Extract the client host from x_forwarded_for header

        In general this is the first "untrusted" host in the forwarded for list.
        """
        x_forwarded_for_hosts = _parse_raw_hosts(x_forwarded_for)

        if self.always_trust:
            return x_forwarded_for_hosts[0]

        # Note: each proxy appends to the header list so check it in reverse order
        #
        # If we have trust_number_of_proxies set, remember that the 'first' one we are skipping is the
        # original source of the request, so we actually remove N-1 proxies from the X-Forwarded-For list.
        x_forwarded_skip = self.trust_number_of_proxies - 1
        if x_forwarded_skip > len(x_forwarded_for_hosts):
            return x_forwarded_for_hosts[0]

        hosts_to_check = x_forwarded_for_hosts[: len(x_forwarded_for_hosts) - x_forwarded_skip]
        for host in reversed(hosts_to_check):
            if host not in self:
                return host

        # All hosts are trusted meaning that the client was also a trusted proxy
        # See https://github.com/encode/uvicorn/issues/1068#issuecomment-855371576
        return x_forwarded_for_hosts[0]
