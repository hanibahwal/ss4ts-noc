from __future__ import annotations

from ipaddress import IPv4Address, IPv4Network, ip_network
from typing import Iterator

from app.models.network_discovery import DiscoveryScope


class NetworkDiscoveryEngine:
    """
    SS4TS Network Discovery CIDR Engine.

    Responsibilities:
    - Validate IPv4 CIDR scopes.
    - Normalize non-canonical CIDR input.
    - Calculate total/usable address counts.
    - Generate usable host addresses lazily.
    """

    MAX_SCAN_ADDRESSES = 65_536

    def parse_network(
        self,
        network_range: str,
    ) -> IPv4Network:
        network = ip_network(
            network_range,
            strict=False,
        )

        if not isinstance(network, IPv4Network):
            raise ValueError(
                "Only IPv4 discovery is currently supported"
            )

        if network.num_addresses > self.MAX_SCAN_ADDRESSES:
            raise ValueError(
                "Discovery range is too large"
            )

        return network

    def normalize_scope(
        self,
        scope: DiscoveryScope,
    ) -> str:
        network = self.parse_network(
            scope.network_range
        )

        return str(network)

    def total_addresses(
        self,
        network_range: str,
    ) -> int:
        return self.parse_network(
            network_range
        ).num_addresses

    def usable_hosts(
        self,
        network_range: str,
    ) -> int:
        network = self.parse_network(
            network_range
        )

        if network.prefixlen == 32:
            return 1

        if network.prefixlen == 31:
            return 2

        return max(
            network.num_addresses - 2,
            0,
        )

    def iter_hosts(
        self,
        network_range: str,
    ) -> Iterator[IPv4Address]:
        network = self.parse_network(
            network_range
        )

        yield from network.hosts()

    def host_strings(
        self,
        network_range: str,
    ) -> list[str]:
        return [
            str(host)
            for host in self.iter_hosts(
                network_range
            )
        ]

    def describe(
        self,
        network_range: str,
    ) -> dict[str, object]:
        network = self.parse_network(
            network_range
        )

        first_host = None
        last_host = None

        if network.prefixlen == 32:
            first_host = network.network_address
            last_host = network.network_address

        elif network.prefixlen == 31:
            first_host = network.network_address
            last_host = network.broadcast_address

        elif network.num_addresses > 2:
            first_host = IPv4Address(
                int(network.network_address) + 1
            )
            last_host = IPv4Address(
                int(network.broadcast_address) - 1
            )

        return {
            "network": str(
                network.network_address
            ),
            "cidr": str(network),
            "prefix_length": (
                network.prefixlen
            ),
            "netmask": str(
                network.netmask
            ),
            "broadcast": str(
                network.broadcast_address
            ),
            "total_addresses": (
                network.num_addresses
            ),
            "usable_hosts": (
                self.usable_hosts(
                    network_range
                )
            ),
            "first_host": (
                str(first_host)
                if first_host
                else None
            ),
            "last_host": (
                str(last_host)
                if last_host
                else None
            ),
        }
