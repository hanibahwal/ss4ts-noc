import pytest

from app.services.network_discovery_engine import (
    NetworkDiscoveryEngine,
)


def test_normalizes_non_canonical_cidr():
    engine = NetworkDiscoveryEngine()

    info = engine.describe(
        "192.168.13.0/22"
    )

    assert info["cidr"] == (
        "192.168.12.0/22"
    )

    assert info["netmask"] == (
        "255.255.252.0"
    )

    assert info["total_addresses"] == 1024
    assert info["usable_hosts"] == 1022

    assert info["first_host"] == (
        "192.168.12.1"
    )

    assert info["last_host"] == (
        "192.168.15.254"
    )


def test_second_example_normalized():
    engine = NetworkDiscoveryEngine()

    info = engine.describe(
        "10.10.10.0/20"
    )

    assert info["cidr"] == (
        "10.10.0.0/20"
    )

    assert info["total_addresses"] == 4096
    assert info["usable_hosts"] == 4094

    assert info["first_host"] == (
        "10.10.0.1"
    )

    assert info["last_host"] == (
        "10.10.15.254"
    )


def test_host_generation():
    engine = NetworkDiscoveryEngine()

    hosts = engine.host_strings(
        "192.168.1.0/30"
    )

    assert hosts == [
        "192.168.1.1",
        "192.168.1.2",
    ]


def test_large_network_rejected():
    engine = NetworkDiscoveryEngine()

    with pytest.raises(
        ValueError,
        match="too large",
    ):
        engine.describe(
            "10.0.0.0/8"
        )


def test_ipv6_rejected():
    engine = NetworkDiscoveryEngine()

    with pytest.raises(
        ValueError,
        match="IPv4",
    ):
        engine.describe(
            "2001:db8::/64"
        )


def test_single_host_scope():
    engine = NetworkDiscoveryEngine()

    info = engine.describe(
        "192.168.45.99/32"
    )

    assert info["total_addresses"] == 1
    assert info["usable_hosts"] == 1
    assert info["first_host"] == (
        "192.168.45.99"
    )
    assert info["last_host"] == (
        "192.168.45.99"
    )
