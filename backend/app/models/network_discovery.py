from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from ipaddress import ip_network
from typing import Any
from uuid import uuid4


class DiscoveryStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DiscoveryMethod(str, Enum):
    ICMP = "ICMP"
    SNMP = "SNMP"
    ROUTEROS_API = "ROUTEROS_API"
    HTTP = "HTTP"
    SSH = "SSH"


@dataclass(frozen=True)
class DiscoveryScope:
    name: str
    network_range: str
    methods: tuple[DiscoveryMethod, ...] = (
        DiscoveryMethod.ICMP,
    )

    def __post_init__(self) -> None:
        network = ip_network(
            self.network_range,
            strict=False,
        )

        if network.num_addresses > 65536:
            raise ValueError(
                "Discovery range is too large"
            )


@dataclass
class DiscoveryJob:
    scope: DiscoveryScope
    job_id: str = field(
        default_factory=lambda:
        f"DISC-{uuid4().hex}"
    )

    status: DiscoveryStatus = (
        DiscoveryStatus.PENDING
    )

    created_at: datetime = field(
        default_factory=lambda:
        datetime.now(timezone.utc)
    )

    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    ip_address: str
    discovered: bool
    vendor: str | None = None
    model: str | None = None
    device_type: str | None = None
    confidence: int = 0
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
