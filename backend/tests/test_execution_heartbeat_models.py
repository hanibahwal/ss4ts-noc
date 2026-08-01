from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.execution_heartbeat import (
    ExecutionWorkerHeartbeat,
    WorkerHeartbeatOwnerMismatch,
    WorkerHeartbeatStatus,
    WorkerHeartbeatVersionConflict,
)


def make_heartbeat(
    **overrides,
) -> ExecutionWorkerHeartbeat:
    now = datetime.now(
        timezone.utc
    )

    values = {
        "worker_id":
            "worker:1",
        "lease_id":
            "lease:1",
        "authorization_id":
            "authorization:1",
        "owner_id":
            "worker:1",
        "status":
            WorkerHeartbeatStatus.HEALTHY,
        "registered_at":
            now,
        "last_heartbeat_at":
            now,
        "heartbeat_interval_seconds":
            15,
        "heartbeat_timeout_seconds":
            45,
        "heartbeat_version":
            1,
        "metadata": {
            "execution_enabled":
                False,
        },
    }

    values.update(
        overrides
    )

    return ExecutionWorkerHeartbeat(
        **values
    )


def test_fresh_heartbeat_is_healthy() -> None:
    heartbeat = make_heartbeat()

    assert heartbeat.is_healthy is True
    assert heartbeat.is_stale is False

    assert (
        heartbeat.effective_status()
        == WorkerHeartbeatStatus.HEALTHY
    )


def test_heartbeat_becomes_degraded() -> None:
    now = datetime.now(
        timezone.utc
    )

    heartbeat = make_heartbeat(
        registered_at=(
            now
            - timedelta(seconds=20)
        ),
        last_heartbeat_at=(
            now
            - timedelta(seconds=20)
        ),
    )

    assert (
        heartbeat.effective_status(
            now=now
        )
        == WorkerHeartbeatStatus.DEGRADED
    )

    assert heartbeat.is_stale_at(
        now=now
    ) is False


def test_heartbeat_becomes_stale() -> None:
    now = datetime.now(
        timezone.utc
    )

    heartbeat = make_heartbeat(
        registered_at=(
            now
            - timedelta(seconds=60)
        ),
        last_heartbeat_at=(
            now
            - timedelta(seconds=60)
        ),
    )

    assert heartbeat.is_stale_at(
        now=now
    ) is True

    assert (
        heartbeat.effective_status(
            now=now
        )
        == WorkerHeartbeatStatus.STALE
    )

    assert (
        heartbeat.can_recover_lease
        is True
    )


def test_stale_boundary_is_inclusive() -> None:
    now = datetime.now(
        timezone.utc
    )

    heartbeat = make_heartbeat(
        registered_at=(
            now
            - timedelta(seconds=45)
        ),
        last_heartbeat_at=(
            now
            - timedelta(seconds=45)
        ),
    )

    assert heartbeat.is_stale_at(
        now=now
    ) is True


def test_stopped_worker_is_not_stale() -> None:
    now = datetime.now(
        timezone.utc
    )

    heartbeat = make_heartbeat(
        status=(
            WorkerHeartbeatStatus.STOPPED
        ),
        registered_at=(
            now
            - timedelta(seconds=120)
        ),
        last_heartbeat_at=(
            now
            - timedelta(seconds=100)
        ),
        stopped_at=(
            now
            - timedelta(seconds=90)
        ),
    )

    assert heartbeat.is_stale_at(
        now=now
    ) is False

    assert (
        heartbeat.effective_status(
            now=now
        )
        == WorkerHeartbeatStatus.STOPPED
    )

    assert heartbeat.can_heartbeat is False


def test_timeout_must_exceed_interval() -> None:
    with pytest.raises(
        ValueError,
        match="greater",
    ):
        make_heartbeat(
            heartbeat_interval_seconds=30,
            heartbeat_timeout_seconds=30,
        )


def test_last_heartbeat_cannot_precede_registration() -> None:
    now = datetime.now(
        timezone.utc
    )

    with pytest.raises(
        ValueError,
        match="last_heartbeat_at",
    ):
        make_heartbeat(
            registered_at=now,
            last_heartbeat_at=(
                now
                - timedelta(seconds=1)
            ),
        )


def test_stopped_requires_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="stopped_at",
    ):
        make_heartbeat(
            status=(
                WorkerHeartbeatStatus.STOPPED
            ),
            stopped_at=None,
        )


def test_version_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="heartbeat_version",
    ):
        make_heartbeat(
            heartbeat_version=0
        )


def test_serialization() -> None:
    payload = make_heartbeat().to_dict()

    assert payload["worker_id"] == "worker:1"

    assert (
        payload["effective_status"]
        == "healthy"
    )

    assert payload["heartbeat_version"] == 1

    assert (
        payload["metadata"]
        ["execution_enabled"]
        is False
    )


def test_owner_mismatch_details() -> None:
    error = WorkerHeartbeatOwnerMismatch(
        worker_id="worker:2",
        lease_owner_id="worker:1",
    )

    assert error.worker_id == "worker:2"

    assert (
        error.lease_owner_id
        == "worker:1"
    )

    assert "does not match" in str(
        error
    )


def test_version_conflict_details() -> None:
    error = WorkerHeartbeatVersionConflict(
        worker_id="worker:1",
        expected_version=1,
        actual_version=2,
    )

    assert error.expected_version == 1
    assert error.actual_version == 2

    assert "expected=1" in str(error)
    assert "actual=2" in str(error)
