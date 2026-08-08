from datetime import timezone

import pytest

from app.models.network_discovery import (
    DiscoveryMethod,
    DiscoveryScope,
    DiscoveryStatus,
    DiscoveryJob,
    DiscoveryResult,
)


def test_valid_cidr_scope():
    scope = DiscoveryScope(
        name="TEST-NETWORK",
        network_range="192.168.13.0/22",
        methods=(
            DiscoveryMethod.ICMP,
            DiscoveryMethod.SNMP,
        ),
    )

    assert scope.network_range == (
        "192.168.13.0/22"
    )


def test_large_network_rejected():
    with pytest.raises(
        ValueError,
        match="too large",
    ):
        DiscoveryScope(
            name="BIG",
            network_range="10.0.0.0/8",
        )


def test_discovery_job_created():
    scope = DiscoveryScope(
        name="LAB",
        network_range="10.10.10.0/24",
    )

    job = DiscoveryJob(
        scope=scope
    )

    assert job.status == (
        DiscoveryStatus.PENDING
    )

    assert job.job_id.startswith(
        "DISC-"
    )


def test_discovery_result():
    result = DiscoveryResult(
        ip_address="192.168.13.1",
        discovered=True,
        vendor="MikroTik",
        confidence=99,
    )

    assert result.vendor == "MikroTik"
    assert result.confidence == 99
