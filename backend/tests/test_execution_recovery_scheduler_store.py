from __future__ import annotations

import sqlite3

import pytest

from app.models.execution_recovery_scheduler import (
    RecoverySchedulerRunStatus,
    RecoverySchedulerStatus,
    RecoverySchedulerVersionConflict,
)
from app.services.execution_recovery_scheduler_store import (
    DEFAULT_RECOVERY_SCHEDULER_ID,
    ExecutionRecoverySchedulerStore,
)


def make_store(
    tmp_path,
) -> ExecutionRecoverySchedulerStore:
    return ExecutionRecoverySchedulerStore(
        tmp_path
        / "execution-authorization.db"
    )


def test_schema_is_created(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

    assert (
        "execution_recovery_schedulers"
        in tables
    )

    assert (
        "execution_recovery_scheduler_events"
        in tables
    )


def test_create_default_scheduler(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    scheduler = store.create_default()

    assert (
        scheduler.scheduler_id
        == DEFAULT_RECOVERY_SCHEDULER_ID
    )

    assert scheduler.enabled is False

    assert (
        scheduler.status
        == RecoverySchedulerStatus.DISABLED
    )

    assert scheduler.scheduler_version == 1

    assert (
        scheduler.metadata[
            "scheduler_enabled"
        ]
        is False
    )


def test_create_default_is_idempotent(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    first = store.create_default()
    second = store.create_default()

    assert (
        second.scheduler_id
        == first.scheduler_id
    )

    assert (
        len(
            store.events()
        )
        == 1
    )


def test_enable_scheduler(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    scheduler = store.enable(
        expected_version=1
    )

    assert scheduler.enabled is True

    assert (
        scheduler.status
        == RecoverySchedulerStatus.IDLE
    )

    assert scheduler.scheduler_version == 2
    assert scheduler.next_run_at is not None


def test_disable_scheduler(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    enabled = store.enable(
        expected_version=1
    )

    disabled = store.disable(
        expected_version=
            enabled.scheduler_version
    )

    assert disabled.enabled is False

    assert (
        disabled.status
        == RecoverySchedulerStatus.DISABLED
    )

    assert disabled.next_run_at is None


def test_version_conflict(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    store.enable(
        expected_version=1
    )

    with pytest.raises(
        RecoverySchedulerVersionConflict,
    ) as exc:
        store.disable(
            expected_version=1
        )

    assert exc.value.actual_version == 2


def test_update_configuration(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    scheduler = store.update_configuration(
        expected_version=1,
        interval_seconds=120,
        batch_size=50,
    )

    assert scheduler.interval_seconds == 120
    assert scheduler.batch_size == 50
    assert scheduler.scheduler_version == 2


def test_run_lifecycle(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    enabled = store.enable(
        expected_version=1
    )

    running = store.mark_run_started(
        expected_version=
            enabled.scheduler_version
    )

    assert (
        running.status
        == RecoverySchedulerStatus.RUNNING
    )

    completed = store.mark_run_completed(
        expected_version=
            running.scheduler_version,
        recovered=2,
        skipped=1,
        failed=0,
    )

    assert (
        completed.status
        == RecoverySchedulerStatus.IDLE
    )

    assert (
        completed.last_run_status
        == RecoverySchedulerRunStatus.SUCCEEDED
    )

    assert completed.last_run_recovered == 2
    assert completed.last_run_skipped == 1
    assert completed.total_runs == 1
    assert completed.total_recovered == 2


def test_partial_run(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    enabled = store.enable(
        expected_version=1
    )

    running = store.mark_run_started(
        expected_version=
            enabled.scheduler_version
    )

    completed = store.mark_run_completed(
        expected_version=
            running.scheduler_version,
        recovered=1,
        skipped=1,
        failed=1,
    )

    assert (
        completed.last_run_status
        == RecoverySchedulerRunStatus.PARTIAL
    )

    assert completed.total_failed == 1


def test_failed_run(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    enabled = store.enable(
        expected_version=1
    )

    running = store.mark_run_started(
        expected_version=
            enabled.scheduler_version
    )

    failed = store.mark_run_failed(
        expected_version=
            running.scheduler_version,
        error_message="Recovery failed",
    )

    assert (
        failed.status
        == RecoverySchedulerStatus.FAILED
    )

    assert (
        failed.last_run_status
        == RecoverySchedulerRunStatus.FAILED
    )

    assert failed.last_error == "Recovery failed"
    assert failed.total_runs == 1
    assert failed.total_failed == 1


def test_disabled_scheduler_cannot_run(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    with pytest.raises(
        ValueError,
        match="Disabled",
    ):
        store.mark_run_started(
            expected_version=1
        )


def test_event_history(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.create_default()

    enabled = store.enable(
        expected_version=1
    )

    configured = (
        store.update_configuration(
            expected_version=
                enabled.scheduler_version,
            interval_seconds=120,
        )
    )

    running = store.mark_run_started(
        expected_version=
            configured.scheduler_version
    )

    store.mark_run_completed(
        expected_version=
            running.scheduler_version,
        recovered=1,
        skipped=0,
        failed=0,
    )

    assert [
        event["event_type"]
        for event in store.events()
    ] == [
        "created",
        "enabled",
        "configuration_updated",
        "run_started",
        "run_completed",
    ]


def test_safety_metadata(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    scheduler = store.create_default()

    assert (
        scheduler.metadata[
            "scheduler_enabled"
        ]
        is False
    )

    assert (
        scheduler.metadata[
            "execution_enabled"
        ]
        is False
    )

    assert (
        scheduler.metadata[
            "network_io_performed"
        ]
        is False
    )

    assert (
        scheduler.metadata[
            "device_command_executed"
        ]
        is False
    )
