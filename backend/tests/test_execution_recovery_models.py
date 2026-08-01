from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.execution_recovery import (
    ExecutionRecovery,
    RecoveryDecision,
    RecoveryReason,
    RecoveryStatus,
    RecoveryVersionConflict,
)


def make_recovery(
    **overrides,
) -> ExecutionRecovery:
    now = datetime.now(
        timezone.utc
    )

    values = {
        "recovery_id":
            "recovery:1",
        "worker_id":
            "worker:1",
        "lease_id":
            "lease:1",
        "authorization_id":
            "authorization:1",
        "status":
            RecoveryStatus.PENDING,
        "decision":
            RecoveryDecision.REVOKE_LEASE,
        "reason":
            RecoveryReason.WORKER_STALE,
        "detected_at":
            now,
        "recovery_version":
            1,
        "metadata": {
            "execution_enabled":
                False,
        },
    }

    values.update(
        overrides
    )

    # Some tests calculate completed_at immediately before calling
    # this helper. Without an explicit detected_at, the helper's
    # internal timestamp can be a few microseconds later and create
    # an invalid completed_at < detected_at ordering.
    if (
        overrides.get("completed_at")
        is not None
        and "detected_at"
        not in overrides
    ):
        values["detected_at"] = (
            overrides["completed_at"]
        )

    return ExecutionRecovery(
        **values
    )


def test_pending_recovery() -> None:
    recovery = make_recovery()

    assert recovery.is_complete is False
    assert recovery.succeeded is False
    assert recovery.completed_at is None


def test_successful_recovery() -> None:
    now = datetime.now(
        timezone.utc
    )

    recovery = make_recovery(
        status=RecoveryStatus.RECOVERED,
        completed_at=now,
        previous_lease_version=1,
        current_lease_version=2,
        previous_heartbeat_version=1,
        current_heartbeat_version=2,
    )

    assert recovery.is_complete is True
    assert recovery.succeeded is True

    assert (
        recovery.lease_version_advanced
        is True
    )

    assert (
        recovery.heartbeat_version_advanced
        is True
    )


def test_skipped_recovery() -> None:
    recovery = make_recovery(
        status=RecoveryStatus.SKIPPED,
        decision=RecoveryDecision.NO_ACTION,
        reason=RecoveryReason.LEASE_NOT_ACTIVE,
        completed_at=datetime.now(
            timezone.utc
        ),
    )

    assert recovery.is_complete is True
    assert recovery.succeeded is False


def test_failed_recovery_requires_error() -> None:
    with pytest.raises(
        ValueError,
        match="error_message",
    ):
        make_recovery(
            status=RecoveryStatus.FAILED,
            completed_at=datetime.now(
                timezone.utc
            ),
            error_message=None,
        )


def test_recovered_requires_valid_decision() -> None:
    with pytest.raises(
        ValueError,
        match="lease recovery decision",
    ):
        make_recovery(
            status=RecoveryStatus.RECOVERED,
            decision=RecoveryDecision.NO_ACTION,
            completed_at=datetime.now(
                timezone.utc
            ),
        )


def test_completed_status_requires_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="completed_at",
    ):
        make_recovery(
            status=RecoveryStatus.SKIPPED,
            completed_at=None,
        )


def test_completion_cannot_precede_detection() -> None:
    now = datetime.now(
        timezone.utc
    )

    with pytest.raises(
        ValueError,
        match="before",
    ):
        make_recovery(
            status=RecoveryStatus.SKIPPED,
            detected_at=now,
            completed_at=(
                now
                - timedelta(seconds=1)
            ),
            decision=RecoveryDecision.NO_ACTION,
            reason=RecoveryReason.LEASE_NOT_ACTIVE,
        )


def test_version_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="recovery_version",
    ):
        make_recovery(
            recovery_version=0
        )


def test_serialization() -> None:
    payload = make_recovery().to_dict()

    assert payload["recovery_id"] == "recovery:1"

    assert (
        payload["reason"]
        == "worker_stale"
    )

    assert payload["is_complete"] is False

    assert (
        payload["metadata"]
        ["execution_enabled"]
        is False
    )


def test_version_conflict_details() -> None:
    error = RecoveryVersionConflict(
        recovery_id="recovery:1",
        expected_version=1,
        actual_version=2,
    )

    assert (
        error.recovery_id
        == "recovery:1"
    )

    assert error.expected_version == 1
    assert error.actual_version == 2

    assert "expected=1" in str(error)
    assert "actual=2" in str(error)
