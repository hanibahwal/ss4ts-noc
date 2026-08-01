from __future__ import annotations

from dataclasses import dataclass, field
from datetime import (
    datetime,
    timezone,
)
from enum import StrEnum
from typing import Any


class RecoveryStatus(StrEnum):
    PENDING = "pending"
    RECOVERED = "recovered"
    SKIPPED = "skipped"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RecoveryDecision(StrEnum):
    REVOKE_LEASE = "revoke_lease"
    EXPIRE_LEASE = "expire_lease"
    NO_ACTION = "no_action"
    RETRY = "retry"
    UNKNOWN = "unknown"


class RecoveryReason(StrEnum):
    WORKER_STALE = "worker_stale"
    LEASE_EXPIRED = "lease_expired"
    LEASE_NOT_ACTIVE = "lease_not_active"
    HEARTBEAT_STOPPED = "heartbeat_stopped"
    OWNER_MISMATCH = "owner_mismatch"
    VERSION_CONFLICT = "version_conflict"
    INTERNAL_ERROR = "internal_error"
    UNKNOWN = "unknown"


class ExecutionRecoveryError(
    RuntimeError
):
    """
    Base class for execution recovery failures.
    """


class RecoveryVersionConflict(
    ExecutionRecoveryError
):
    def __init__(
        self,
        *,
        recovery_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.recovery_id = str(
            recovery_id
        ).strip()

        self.expected_version = int(
            expected_version
        )

        self.actual_version = int(
            actual_version
        )

        super().__init__(
            "Execution recovery version conflict: "
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
                "Recovery datetime is required"
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


@dataclass(slots=True)
class ExecutionRecovery:
    recovery_id: str

    worker_id: str

    lease_id: str

    authorization_id: str

    status: RecoveryStatus

    decision: RecoveryDecision

    reason: RecoveryReason

    detected_at: datetime

    completed_at: datetime | None = None

    previous_lease_version: int | None = None

    current_lease_version: int | None = None

    previous_heartbeat_version: int | None = None

    current_heartbeat_version: int | None = None

    recovery_version: int = 1

    error_message: str | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.recovery_id = _text(
            self.recovery_id
        )

        self.worker_id = _text(
            self.worker_id
        )

        self.lease_id = _text(
            self.lease_id
        )

        self.authorization_id = _text(
            self.authorization_id
        )

        try:
            self.status = (
                self.status
                if isinstance(
                    self.status,
                    RecoveryStatus,
                )
                else RecoveryStatus(
                    _text(
                        self.status
                    ).lower()
                )
            )
        except ValueError:
            self.status = (
                RecoveryStatus.UNKNOWN
            )

        try:
            self.decision = (
                self.decision
                if isinstance(
                    self.decision,
                    RecoveryDecision,
                )
                else RecoveryDecision(
                    _text(
                        self.decision
                    ).lower()
                )
            )
        except ValueError:
            self.decision = (
                RecoveryDecision.UNKNOWN
            )

        try:
            self.reason = (
                self.reason
                if isinstance(
                    self.reason,
                    RecoveryReason,
                )
                else RecoveryReason(
                    _text(
                        self.reason
                    ).lower()
                )
            )
        except ValueError:
            self.reason = (
                RecoveryReason.UNKNOWN
            )

        self.detected_at = _datetime(
            self.detected_at
        )

        if self.completed_at is not None:
            self.completed_at = _datetime(
                self.completed_at
            )

        self.recovery_version = int(
            self.recovery_version
        )

        self.error_message = (
            _text(
                self.error_message
            )
            or None
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.recovery_id:
            raise ValueError(
                "recovery_id must not be empty"
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

        if self.status == RecoveryStatus.UNKNOWN:
            raise ValueError(
                "Recovery status must be known"
            )

        if self.decision == RecoveryDecision.UNKNOWN:
            raise ValueError(
                "Recovery decision must be known"
            )

        if self.reason == RecoveryReason.UNKNOWN:
            raise ValueError(
                "Recovery reason must be known"
            )

        if self.recovery_version < 1:
            raise ValueError(
                "recovery_version must be at least 1"
            )

        if (
            self.completed_at is not None
            and self.completed_at
            < self.detected_at
        ):
            raise ValueError(
                "completed_at cannot be before "
                "detected_at"
            )

        if (
            self.status
            in {
                RecoveryStatus.RECOVERED,
                RecoveryStatus.SKIPPED,
                RecoveryStatus.FAILED,
            }
            and self.completed_at is None
        ):
            raise ValueError(
                "Completed recovery status "
                "requires completed_at"
            )

        if (
            self.status
            == RecoveryStatus.FAILED
            and not self.error_message
        ):
            raise ValueError(
                "Failed recovery requires "
                "error_message"
            )

        if (
            self.status
            == RecoveryStatus.RECOVERED
            and self.decision
            not in {
                RecoveryDecision.REVOKE_LEASE,
                RecoveryDecision.EXPIRE_LEASE,
            }
        ):
            raise ValueError(
                "Recovered status requires "
                "a lease recovery decision"
            )

    @property
    def is_complete(
        self,
    ) -> bool:
        return self.status in {
            RecoveryStatus.RECOVERED,
            RecoveryStatus.SKIPPED,
            RecoveryStatus.FAILED,
        }

    @property
    def succeeded(
        self,
    ) -> bool:
        return (
            self.status
            == RecoveryStatus.RECOVERED
        )

    @property
    def lease_version_advanced(
        self,
    ) -> bool:
        return bool(
            self.previous_lease_version
            is not None
            and self.current_lease_version
            is not None
            and self.current_lease_version
            > self.previous_lease_version
        )

    @property
    def heartbeat_version_advanced(
        self,
    ) -> bool:
        return bool(
            self.previous_heartbeat_version
            is not None
            and self.current_heartbeat_version
            is not None
            and self.current_heartbeat_version
            > self.previous_heartbeat_version
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "recovery_id":
                self.recovery_id,
            "worker_id":
                self.worker_id,
            "lease_id":
                self.lease_id,
            "authorization_id":
                self.authorization_id,
            "status":
                self.status.value,
            "decision":
                self.decision.value,
            "reason":
                self.reason.value,
            "detected_at":
                self.detected_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
            "previous_lease_version":
                self.previous_lease_version,
            "current_lease_version":
                self.current_lease_version,
            "previous_heartbeat_version":
                self.previous_heartbeat_version,
            "current_heartbeat_version":
                self.current_heartbeat_version,
            "recovery_version":
                self.recovery_version,
            "error_message":
                self.error_message,
            "is_complete":
                self.is_complete,
            "succeeded":
                self.succeeded,
            "lease_version_advanced":
                self.lease_version_advanced,
            "heartbeat_version_advanced":
                self.heartbeat_version_advanced,
            "metadata":
                dict(self.metadata),
        }
