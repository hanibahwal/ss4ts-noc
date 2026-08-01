from __future__ import annotations

from dataclasses import dataclass, field
from datetime import (
    datetime,
    timezone,
)
from enum import StrEnum
from typing import Any


class ExecutionLeaseStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class ExecutionLeaseError(
    RuntimeError
):
    """
    Base class for execution-lease failures.
    """


class LeaseConflict(
    ExecutionLeaseError
):
    def __init__(
        self,
        *,
        authorization_id: str,
        owner_id: str | None = None,
    ) -> None:
        self.authorization_id = str(
            authorization_id
        ).strip()

        self.owner_id = (
            str(owner_id).strip()
            if owner_id is not None
            else None
        )

        message = (
            "An active execution lease "
            "already exists"
        )

        if self.owner_id:
            message += (
                f" for owner={self.owner_id}"
            )

        super().__init__(message)


class LeaseTokenMismatch(
    ExecutionLeaseError
):
    def __init__(
        self,
        *,
        lease_id: str,
    ) -> None:
        self.lease_id = str(
            lease_id
        ).strip()

        super().__init__(
            "Execution lease token mismatch"
        )


class LeaseVersionConflict(
    ExecutionLeaseError
):
    def __init__(
        self,
        *,
        lease_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.lease_id = str(
            lease_id
        ).strip()

        self.expected_version = int(
            expected_version
        )

        self.actual_version = int(
            actual_version
        )

        super().__init__(
            "Execution lease version conflict: "
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
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)

        if not text:
            return datetime.now(
                timezone.utc
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

    return parsed


@dataclass(slots=True)
class ExecutionLease:
    lease_id: str
    authorization_id: str
    lease_token: str
    owner_id: str

    status: ExecutionLeaseStatus

    acquired_at: datetime
    expires_at: datetime

    renewed_at: datetime | None = None
    released_at: datetime | None = None

    lease_version: int = 1

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.lease_id = _text(
            self.lease_id
        )

        self.authorization_id = _text(
            self.authorization_id
        )

        self.lease_token = _text(
            self.lease_token
        )

        self.owner_id = _text(
            self.owner_id
        )

        try:
            self.status = (
                self.status
                if isinstance(
                    self.status,
                    ExecutionLeaseStatus,
                )
                else ExecutionLeaseStatus(
                    _text(
                        self.status
                    ).lower()
                )
            )
        except ValueError:
            self.status = (
                ExecutionLeaseStatus.UNKNOWN
            )

        self.acquired_at = _datetime(
            self.acquired_at
        )

        self.expires_at = _datetime(
            self.expires_at
        )

        if self.renewed_at is not None:
            self.renewed_at = _datetime(
                self.renewed_at
            )

        if self.released_at is not None:
            self.released_at = _datetime(
                self.released_at
            )

        self.lease_version = int(
            self.lease_version
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.lease_id:
            raise ValueError(
                "lease_id must not be empty"
            )

        if not self.authorization_id:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if not self.lease_token:
            raise ValueError(
                "lease_token must not be empty"
            )

        if not self.owner_id:
            raise ValueError(
                "owner_id must not be empty"
            )

        if (
            self.status
            == ExecutionLeaseStatus.UNKNOWN
        ):
            raise ValueError(
                "Execution lease status "
                "must be known"
            )

        if self.lease_version < 1:
            raise ValueError(
                "lease_version must be at least 1"
            )

        if (
            self.expires_at
            <= self.acquired_at
        ):
            raise ValueError(
                "expires_at must be after "
                "acquired_at"
            )

        if (
            self.status
            == ExecutionLeaseStatus.RELEASED
            and self.released_at is None
        ):
            raise ValueError(
                "Released lease requires "
                "released_at"
            )

    @property
    def is_expired(
        self,
    ) -> bool:
        return (
            datetime.now(
                timezone.utc
            )
            >= self.expires_at
        )

    @property
    def is_active(
        self,
    ) -> bool:
        return (
            self.status
            == ExecutionLeaseStatus.ACTIVE
            and not self.is_expired
        )

    @property
    def is_released(
        self,
    ) -> bool:
        return (
            self.status
            == ExecutionLeaseStatus.RELEASED
        )

    @property
    def can_renew(
        self,
    ) -> bool:
        return self.is_active

    @property
    def can_release(
        self,
    ) -> bool:
        return self.is_active

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "lease_id":
                self.lease_id,
            "authorization_id":
                self.authorization_id,
            "lease_token":
                self.lease_token,
            "owner_id":
                self.owner_id,
            "status":
                self.status.value,
            "acquired_at":
                self.acquired_at.isoformat(),
            "expires_at":
                self.expires_at.isoformat(),
            "renewed_at": (
                self.renewed_at.isoformat()
                if self.renewed_at
                else None
            ),
            "released_at": (
                self.released_at.isoformat()
                if self.released_at
                else None
            ),
            "lease_version":
                self.lease_version,
            "is_expired":
                self.is_expired,
            "is_active":
                self.is_active,
            "is_released":
                self.is_released,
            "can_renew":
                self.can_renew,
            "can_release":
                self.can_release,
            "metadata":
                dict(self.metadata),
        }
