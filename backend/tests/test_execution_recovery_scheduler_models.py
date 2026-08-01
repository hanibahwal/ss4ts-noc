from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.execution_recovery_scheduler import (
    ExecutionRecoveryScheduler,
    RecoverySchedulerRunStatus,
    RecoverySchedulerStatus,
    RecoverySchedulerVersionConflict,
)


def make_scheduler(
    **overrides,
) -> ExecutionRecoveryScheduler:
    now = datetime.now(
        timezone.utc
    )

    values = {
        "scheduler_id":
            "recovery-scheduler:default",
        "status":
            RecoverySchedulerStatus.DISABLED,
        "enabled":
            False,
        "interval_seconds":
            60,
        "batch_size":
            100,
        "created_at":
            now,
        "updated_at":
            now,
        "last_run_status":
            RecoverySchedulerRunStatus.NEVER_RUN,
        "scheduler_version":
            1,
        "metadata": {
            "execution_enabled":
                False,
            "scheduler_enabled":
                False,
        },
    }

    values.update(
        overrides
    )

    return ExecutionRecoveryScheduler(
        **values
    )


def test_disabled_scheduler() -> None:
    scheduler = make_scheduler()

    assert scheduler.enabled is False

    assert (
        scheduler.status
        == RecoverySchedulerStatus.DISABLED
    )

    assert scheduler.is_due is False
    assert scheduler.is_running is False
    assert scheduler.has_run is False


def test_enabled_idle_scheduler_is_due_without_next_run() -> None:
    scheduler = make_scheduler(
        enabled=True,
        status=RecoverySchedulerStatus.IDLE,
    )

    assert scheduler.is_due is True


def test_future_scheduler_is_not_due() -> None:
    now = datetime.now(
        timezone.utc
    )

    scheduler = make_scheduler(
        enabled=True,
        status=RecoverySchedulerStatus.IDLE,
        next_run_at=(
            now
            + timedelta(seconds=60)
        ),
    )

    assert scheduler.is_due_at(
        now=now
    ) is False


def test_past_scheduler_is_due() -> None:
    now = datetime.now(
        timezone.utc
    )

    scheduler = make_scheduler(
        enabled=True,
        status=RecoverySchedulerStatus.IDLE,
        next_run_at=(
            now
            - timedelta(seconds=1)
        ),
    )

    assert scheduler.is_due_at(
        now=now
    ) is True


def test_running_scheduler_is_not_due() -> None:
    now = datetime.now(
        timezone.utc
    )

    scheduler = make_scheduler(
        enabled=True,
        status=RecoverySchedulerStatus.RUNNING,
        created_at=now,
        updated_at=now,
        last_run_started_at=now,
        next_run_at=(
            now
            - timedelta(seconds=1)
        ),
    )

    assert scheduler.is_running is True

    assert scheduler.is_due_at(
        now=now
    ) is False


def test_processed_counters() -> None:
    scheduler = make_scheduler(
        enabled=True,
        status=RecoverySchedulerStatus.IDLE,
        total_runs=3,
        last_run_recovered=2,
        last_run_skipped=1,
        last_run_failed=1,
        total_recovered=7,
        total_skipped=2,
        total_failed=1,
        last_run_status=(
            RecoverySchedulerRunStatus.PARTIAL
        ),
    )

    assert scheduler.last_run_processed == 4
    assert scheduler.total_processed == 10
    assert scheduler.has_run is True


def test_calculate_next_run() -> None:
    now = datetime.now(
        timezone.utc
    )

    scheduler = make_scheduler(
        interval_seconds=120,
    )

    assert (
        scheduler.calculate_next_run(
            from_time=now
        )
        == now + timedelta(seconds=120)
    )


def test_failed_run_requires_error() -> None:
    with pytest.raises(
        ValueError,
        match="last_error",
    ):
        make_scheduler(
            status=RecoverySchedulerStatus.FAILED,
            last_run_status=(
                RecoverySchedulerRunStatus.FAILED
            ),
            last_error=None,
        )


def test_disabled_scheduler_rejects_idle_status() -> None:
    with pytest.raises(
        ValueError,
        match="Disabled scheduler",
    ):
        make_scheduler(
            enabled=False,
            status=RecoverySchedulerStatus.IDLE,
        )


def test_enabled_scheduler_rejects_disabled_status() -> None:
    with pytest.raises(
        ValueError,
        match="Enabled scheduler",
    ):
        make_scheduler(
            enabled=True,
            status=RecoverySchedulerStatus.DISABLED,
        )


def test_invalid_interval_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="interval_seconds",
    ):
        make_scheduler(
            interval_seconds=1,
        )


def test_invalid_batch_size_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="batch_size",
    ):
        make_scheduler(
            batch_size=0,
        )


def test_completed_run_requires_start() -> None:
    with pytest.raises(
        ValueError,
        match="requires",
    ):
        make_scheduler(
            last_run_completed_at=
                datetime.now(
                    timezone.utc
                ),
        )


def test_serialization() -> None:
    scheduler = make_scheduler()

    payload = scheduler.to_dict()

    assert (
        payload["scheduler_id"]
        == "recovery-scheduler:default"
    )

    assert payload["status"] == "disabled"
    assert payload["scheduler_version"] == 1
    assert payload["is_due"] is False

    assert (
        payload["metadata"]
        ["execution_enabled"]
        is False
    )


def test_version_conflict_details() -> None:
    error = RecoverySchedulerVersionConflict(
        scheduler_id=
            "recovery-scheduler:default",
        expected_version=1,
        actual_version=2,
    )

    assert (
        error.scheduler_id
        == "recovery-scheduler:default"
    )

    assert error.expected_version == 1
    assert error.actual_version == 2

    assert "expected=1" in str(error)
    assert "actual=2" in str(error)
