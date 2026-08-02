from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.models.notification import (
    NotificationIncident,
)


class IncidentLifecycleAction(StrEnum):
    CREATED = "created"
    OBSERVED = "observed"
    ACKNOWLEDGED = "acknowledged"
    RECOVERED = "recovered"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class IncidentLifecycleError(
    RuntimeError
):
    """Base incident lifecycle failure."""


class InvalidIncidentTransition(
    IncidentLifecycleError
):
    """Requested incident status transition is invalid."""


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentLifecycleResult:
    action: IncidentLifecycleAction

    incident: NotificationIncident | None

    created: bool = False
    changed: bool = False

    previous_status: str | None = None
    current_status: str | None = None

    downtime_seconds: float | None = None

    reason: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentLifecycleSummary:
    incident_id: str
    fingerprint: str

    status: str

    occurrence_count: int
    escalation_level: int

    first_seen_at: datetime
    last_seen_at: datetime

    acknowledged_at: datetime | None
    resolved_at: datetime | None

    downtime_seconds: float | None
