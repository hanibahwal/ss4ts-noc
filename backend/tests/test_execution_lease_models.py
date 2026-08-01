from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.execution_lease import (
    ExecutionLease,
    ExecutionLeaseStatus,
    LeaseConflict,
    LeaseTokenMismatch,
    LeaseVersionConflict,
)


def make_lease(
    **overrides,
) -> ExecutionLease:
    now = datetime.now(
        timezone.utc
    )

    values = {
        "lease_id":
            "lease:1",
        "authorization_id":
            "authorization:1",
        "lease_token":
            "token-123",
        "owner_id":
            "worker:1",
        "status":
            ExecutionLeaseStatus.ACTIVE,
        "acquired_at":
            now,
        "expires_at":
            now + timedelta(minutes=5),
        "lease_version":
            1,
        "metadata": {
            "execution_enabled":
                False,
        },
    }

    values.update(
        overrides
    )

    return ExecutionLease(
        **values
    )


def test_active_lease() -> None:
    lease = make_lease()

    assert lease.is_active is True
    assert lease.is_expired is False
    assert lease.can_renew is True
    assert lease.can_release is True


def test_expired_lease() -> None:
    now = datetime.now(
        timezone.utc
    )

    lease = make_lease(
        acquired_at=(
            now
            - timedelta(minutes=10)
        ),
        expires_at=(
            now
            - timedelta(minutes=1)
        ),
    )

    assert lease.is_expired is True
    assert lease.is_active is False
    assert lease.can_renew is False


def test_released_lease() -> None:
    now = datetime.now(
        timezone.utc
    )

    lease = make_lease(
        status=(
            ExecutionLeaseStatus.RELEASED
        ),
        released_at=now,
    )

    assert lease.is_released is True
    assert lease.is_active is False


def test_released_requires_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="released_at",
    ):
        make_lease(
            status=(
                ExecutionLeaseStatus.RELEASED
            ),
            released_at=None,
        )


def test_expiry_must_follow_acquisition() -> None:
    now = datetime.now(
        timezone.utc
    )

    with pytest.raises(
        ValueError,
        match="expires_at",
    ):
        make_lease(
            acquired_at=now,
            expires_at=now,
        )


def test_version_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="lease_version",
    ):
        make_lease(
            lease_version=0
        )


def test_serialization() -> None:
    payload = make_lease().to_dict()

    assert payload["lease_id"] == "lease:1"
    assert payload["status"] == "active"
    assert payload["lease_version"] == 1

    assert (
        payload["metadata"]
        ["execution_enabled"]
        is False
    )


def test_conflict_details() -> None:
    conflict = LeaseConflict(
        authorization_id=
            "authorization:1",
        owner_id=
            "worker:1",
    )

    assert (
        conflict.authorization_id
        == "authorization:1"
    )

    assert conflict.owner_id == "worker:1"
    assert "already exists" in str(conflict)


def test_token_mismatch_details() -> None:
    mismatch = LeaseTokenMismatch(
        lease_id="lease:1"
    )

    assert mismatch.lease_id == "lease:1"
    assert "token mismatch" in str(mismatch)


def test_version_conflict_details() -> None:
    conflict = LeaseVersionConflict(
        lease_id="lease:1",
        expected_version=1,
        actual_version=2,
    )

    assert conflict.expected_version == 1
    assert conflict.actual_version == 2
    assert "expected=1" in str(conflict)
    assert "actual=2" in str(conflict)
