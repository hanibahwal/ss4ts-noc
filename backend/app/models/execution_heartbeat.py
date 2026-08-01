from __future__ import annotations

from dataclasses import dataclass, field
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import StrEnum
from typing import Any


DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 45


class WorkerHeartbeatStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    STALE = "stale"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class WorkerHeartbeatError(
    RuntimeError
):
    """
    Base class for worker-heartbeat failures.
    """


class WorkerHeartbeatOwnerMismatch(
    WorkerHeartbeatError
):
    def __init__(
        self,
        *,
        worker_id: str,
        lease_owner_id: str,
    ) -> None:
        self.worker_id = str(
            worker_id
        ).strip()

        self.lease_owner_id = str(
            lease_owner_id
        ).strip()

        super().__init__(
            "Worker heartbeat owner does not "
            "match execution lease owner"
        )


class WorkerHeartbeatVersionConflict(
    WorkerHeartbeatError
):
    def __init__(
        self,
        *,
        worker_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.worker_id = str(
            worker_id
        ).strip()

        self.expected_version = int(
            expected_version
        )

        self.actual_version = int(
            actual_version
        )

        super().__init__(
            "Worker heartbeat version conflict: "
            f"expected={self.expected_version}, "
            f"actual={self.actual_version}"
        )


def _text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _datetime(
    value: Any,
) -> datetime:
    if isinstance(
        value,
        datetime,
    ):
        parsed = value
    else:
        text = _text(
            value
        )

        if not text:
            raise ValueError(
                "Heartbeat datetime is required"
            )

        parsed = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _positive_seconds(
    value: Any,
    *,
    field_name: str,
    minimum: int = 1,
    maximum: int = 3600,
) -> int:
    normalized = int(
        value
    )

    if normalized < minimum:
        raise ValueError(
            f"{field_name} must be "
            f"at least {minimum}"
        )

    if normalized > maximum:
        raise ValueError(
            f"{field_name} must not "
            f"exceed {maximum}"
        )

    return normalized


@dataclass(slots=True)
class ExecutionWorkerHeartbeat:
    worker_id: str

    lease_id: str

    authorization_id: str

    owner_id: str

    status: WorkerHeartbeatStatus

    registered_at: datetime

    last_heartbeat_at: datetime

    heartbeat_interval_seconds: int = (
        DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    )

    heartbeat_timeout_seconds: int = (
        DEFAULT_HEARTBEAT_TIMEOUT_SECONDS
    )

    heartbeat_version: int = 1

    stopped_at: datetime | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.worker_id = _text(
            self.worker_id
        )

        self.lease_id = _text(
            self.lease_id
        )

        self.authorization_id = _text(
            self.authorization_id
        )

        self.owner_id = _text(
            self.owner_id
        )

        try:
            self.status = (
                self.status
                if isinstance(
                    self.status,
                    WorkerHeartbeatStatus,
                )
                else WorkerHeartbeatStatus(
                    _text(
                        self.status
                    ).lower()
                )
            )
        except ValueError:
            self.status = (
                WorkerHeartbeatStatus.UNKNOWN
            )

        self.registered_at = _datetime(
            self.registered_at
        )

        self.last_heartbeat_at = _datetime(
            self.last_heartbeat_at
        )

        if self.stopped_at is not None:
            self.stopped_at = _datetime(
                self.stopped_at
            )

        self.heartbeat_interval_seconds = (
            _positive_seconds(
                self.heartbeat_interval_seconds,
                field_name=(
                    "heartbeat_interval_seconds"
                ),
                minimum=1,
                maximum=3600,
            )
        )

        self.heartbeat_timeout_seconds = (
            _positive_seconds(
                self.heartbeat_timeout_seconds,
                field_name=(
                    "heartbeat_timeout_seconds"
                ),
                minimum=2,
                maximum=7200,
            )
        )

        self.heartbeat_version = int(
            self.heartbeat_version
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.worker_id:
            raise ValueError(
                "worker_id must not be empty"
            )

        if not self.lease_id:
            raise ValueError(
                "lease_id must not be empty"
            )

        if not self.authorization_id:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if not self.owner_id:
            raise ValueError(
                "owner_id must not be empty"
            )

        if (
            self.status
            == WorkerHeartbeatStatus.UNKNOWN
        ):
            raise ValueError(
                "Worker heartbeat status "
                "must be known"
            )

        if self.heartbeat_version < 1:
            raise ValueError(
                "heartbeat_version must "
                "be at least 1"
            )

        if (
            self.last_heartbeat_at
            < self.registered_at
        ):
            raise ValueError(
                "last_heartbeat_at cannot be "
                "before registered_at"
            )

        if (
            self.heartbeat_timeout_seconds
            <= self.heartbeat_interval_seconds
        ):
            raise ValueError(
                "heartbeat_timeout_seconds must "
                "be greater than "
                "heartbeat_interval_seconds"
            )

        if (
            self.status
            == WorkerHeartbeatStatus.STOPPED
            and self.stopped_at is None
        ):
            raise ValueError(
                "Stopped heartbeat requires "
                "stopped_at"
            )

        if (
            self.stopped_at is not None
            and self.stopped_at
            < self.registered_at
        ):
            raise ValueError(
                "stopped_at cannot be before "
                "registered_at"
            )

    @property
    def stale_at(
        self,
    ) -> datetime:
        return (
            self.last_heartbeat_at
            + timedelta(
                seconds=(
                    self
                    .heartbeat_timeout_seconds
                )
            )
        )

    def age_seconds(
        self,
        *,
        now: datetime | None = None,
    ) -> float:
        current = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )

        current = _datetime(
            current
        )

        return max(
            0.0,
            (
                current
                - self.last_heartbeat_at
            ).total_seconds(),
        )

    def is_stale_at(
        self,
        *,
        now: datetime | None = None,
    ) -> bool:
        if (
            self.status
            == WorkerHeartbeatStatus.STOPPED
        ):
            return False

        current = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )

        return (
            _datetime(current)
            >= self.stale_at
        )

    def effective_status(
        self,
        *,
        now: datetime | None = None,
    ) -> WorkerHeartbeatStatus:
        if (
            self.status
            == WorkerHeartbeatStatus.STOPPED
        ):
            return (
                WorkerHeartbeatStatus.STOPPED
            )

        if self.is_stale_at(
            now=now
        ):
            return (
                WorkerHeartbeatStatus.STALE
            )

        age = self.age_seconds(
            now=now
        )

        if (
            age
            > self.heartbeat_interval_seconds
        ):
            return (
                WorkerHeartbeatStatus.DEGRADED
            )

        return WorkerHeartbeatStatus.HEALTHY

    @property
    def is_stale(
        self,
    ) -> bool:
        return self.is_stale_at()

    @property
    def is_healthy(
        self,
    ) -> bool:
        return (
            self.effective_status()
            == WorkerHeartbeatStatus.HEALTHY
        )

    @property
    def can_heartbeat(
        self,
    ) -> bool:
        return (
            self.status
            != WorkerHeartbeatStatus.STOPPED
        )

    @property
    def can_recover_lease(
        self,
    ) -> bool:
        return (
            self.effective_status()
            == WorkerHeartbeatStatus.STALE
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        effective_status = (
            self.effective_status()
        )

        return {
            "worker_id":
                self.worker_id,
            "lease_id":
                self.lease_id,
            "authorization_id":
                self.authorization_id,
            "owner_id":
                self.owner_id,
            "status":
                self.status.value,
            "effective_status":
                effective_status.value,
            "registered_at":
                self.registered_at
                .isoformat(),
            "last_heartbeat_at":
                self.last_heartbeat_at
                .isoformat(),
            "heartbeat_interval_seconds":
                self
                .heartbeat_interval_seconds,
            "heartbeat_timeout_seconds":
                self
                .heartbeat_timeout_seconds,
            "stale_at":
                self.stale_at.isoformat(),
            "heartbeat_version":
                self.heartbeat_version,
            "stopped_at": (
                self.stopped_at.isoformat()
                if self.stopped_at
                else None
            ),
            "is_stale":
                self.is_stale,
            "is_healthy":
                self.is_healthy,
            "can_heartbeat":
                self.can_heartbeat,
            "can_recover_lease":
                self.can_recover_lease,
            "metadata":
                dict(self.metadata),
        }
