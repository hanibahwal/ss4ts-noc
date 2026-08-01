from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import sqlite3

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
)
from app.models.execution_recovery_scheduler import (
    RecoverySchedulerRunStatus,
    RecoverySchedulerStatus,
)
from app.services.execution_authorization import (
    build_execution_authorization,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_heartbeat_store import (
    ExecutionHeartbeatStore,
)
from app.services.execution_lease_store import (
    ExecutionLeaseStore,
)
from app.services.execution_recovery import (
    ExecutionRecoveryService,
)
from app.services.execution_recovery_scheduler import (
    ExecutionRecoverySchedulerService,
    RecoverySchedulerExecutionResult,
)
from app.services.execution_recovery_scheduler_store import (
    ExecutionRecoverySchedulerStore,
)
from tests.test_execution_simulator import (
    make_plan,
)


def requester() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:hani",
        display_name="Hani",
        role=ApprovalRole.NETWORK_ENGINEER,
    )


def senior() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:senior",
        display_name="Senior Engineer",
        role=ApprovalRole.SENIOR_ENGINEER,
    )


def make_environment(
    tmp_path,
):
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    authorization_store = (
        ExecutionAuthorizationStore(
            database
        )
    )

    lease_store = ExecutionLeaseStore(
        database
    )

    heartbeat_store = (
        ExecutionHeartbeatStore(
            database
        )
    )

    recovery_service = (
        ExecutionRecoveryService(
            database
        )
    )

    scheduler_store = (
        ExecutionRecoverySchedulerStore(
            database
        )
    )

    scheduler_service = (
        ExecutionRecoverySchedulerService(
            database,
            scheduler_store=
                scheduler_store,
            recovery_service=
                recovery_service,
        )
    )

    authorization = (
        authorization_store.create(
            build_execution_authorization(
                make_plan(),
                requester=requester(),
            )
        )
    )

    authorization_store.approve_atomic(
        authorization.authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=(
            "approve-scheduler-service-001"
        ),
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
        ttl_seconds=300,
    )

    heartbeat = heartbeat_store.register_worker(
        worker_id="worker:1",
        lease_id=lease.lease_id,
        heartbeat_interval_seconds=5,
        heartbeat_timeout_seconds=10,
    )

    scheduler = scheduler_store.create_default(
        interval_seconds=60,
        batch_size=100,
    )

    return {
        "database":
            database,
        "authorization_store":
            authorization_store,
        "lease_store":
            lease_store,
        "heartbeat_store":
            heartbeat_store,
        "recovery_service":
            recovery_service,
        "scheduler_store":
            scheduler_store,
        "scheduler_service":
            scheduler_service,
        "authorization":
            authorization,
        "lease":
            lease,
        "heartbeat":
            heartbeat,
        "scheduler":
            scheduler,
    }


def enable_scheduler(
    environment,
):
    scheduler = environment[
        "scheduler_store"
    ].get()

    assert scheduler is not None

    return environment[
        "scheduler_store"
    ].enable(
        expected_version=
            scheduler.scheduler_version
    )


def make_worker_stale(
    environment,
) -> None:
    stale_time = (
        datetime.now(
            timezone.utc
        )
        - timedelta(seconds=30)
    )

    with sqlite3.connect(
        environment["database"]
    ) as connection:
        connection.execute(
            """
            UPDATE execution_heartbeats
            SET
                registered_at = ?,
                last_heartbeat_at = ?
            WHERE worker_id = ?
            """,
            (
                stale_time.isoformat(),
                stale_time.isoformat(),
                environment[
                    "heartbeat"
                ].worker_id,
            ),
        )

        connection.commit()


def make_scheduler_due(
    environment,
) -> None:
    due_time = (
        datetime.now(
            timezone.utc
        )
        - timedelta(seconds=1)
    )

    with sqlite3.connect(
        environment["database"]
    ) as connection:
        connection.execute(
            """
            UPDATE execution_recovery_schedulers
            SET next_run_at = ?
            WHERE scheduler_id = ?
            """,
            (
                due_time.isoformat(),
                environment[
                    "scheduler"
                ].scheduler_id,
            ),
        )

        connection.commit()


def test_disabled_scheduler_is_skipped(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    result = environment[
        "scheduler_service"
    ].run_once()

    assert isinstance(
        result,
        RecoverySchedulerExecutionResult,
    )

    assert result.executed is False

    assert (
        result.reason
        == "scheduler_disabled"
    )


def test_not_due_scheduler_is_skipped(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    enable_scheduler(
        environment
    )

    result = environment[
        "scheduler_service"
    ].run_once()

    assert result.executed is False

    assert (
        result.reason
        == "scheduler_not_due"
    )


def test_force_runs_not_due_scheduler(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    enable_scheduler(
        environment
    )

    result = environment[
        "scheduler_service"
    ].run_once(
        force=True
    )

    assert result.executed is True
    assert result.reason == "run_completed"
    assert result.processed == 0

    assert result.scheduler is not None

    assert (
        result.scheduler.last_run_status
        == RecoverySchedulerRunStatus.SUCCEEDED
    )


def test_due_scheduler_recovers_stale_worker(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    enable_scheduler(
        environment
    )

    make_scheduler_due(
        environment
    )

    make_worker_stale(
        environment
    )

    result = environment[
        "scheduler_service"
    ].run_once()

    assert result.executed is True
    assert result.succeeded is True
    assert result.recovered == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert result.processed == 1

    assert result.scheduler is not None

    assert (
        result.scheduler.status
        == RecoverySchedulerStatus.IDLE
    )

    assert result.scheduler.total_runs == 1
    assert result.scheduler.total_recovered == 1


def test_run_updates_event_history(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    enable_scheduler(
        environment
    )

    make_worker_stale(
        environment
    )

    environment[
        "scheduler_service"
    ].run_once(
        force=True
    )

    event_types = [
        event["event_type"]
        for event in environment[
            "scheduler_store"
        ].events()
    ]

    assert event_types == [
        "created",
        "enabled",
        "run_started",
        "run_completed",
    ]


def test_running_scheduler_is_not_started_again(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    enabled = enable_scheduler(
        environment
    )

    environment[
        "scheduler_store"
    ].mark_run_started(
        expected_version=
            enabled.scheduler_version
    )

    result = environment[
        "scheduler_service"
    ].run_once(
        force=True
    )

    assert result.executed is False

    assert (
        result.reason
        == "scheduler_already_running"
    )


def test_recovery_failure_marks_scheduler_failed(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_environment(
        tmp_path
    )

    enable_scheduler(
        environment
    )

    def fail_recovery(
        *,
        limit: int,
    ):
        raise RuntimeError(
            "Simulated recovery failure"
        )

    monkeypatch.setattr(
        environment[
            "recovery_service"
        ],
        "recover_stale_workers",
        fail_recovery,
    )

    result = environment[
        "scheduler_service"
    ].run_once(
        force=True
    )

    assert result.executed is True
    assert result.succeeded is False
    assert result.reason == "run_failed"

    assert (
        result.error_message
        == "Simulated recovery failure"
    )

    assert result.scheduler is not None

    assert (
        result.scheduler.status
        == RecoverySchedulerStatus.FAILED
    )

    assert (
        result.scheduler.last_run_status
        == RecoverySchedulerRunStatus.FAILED
    )


def test_result_serialization(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    result = environment[
        "scheduler_service"
    ].run_once()

    payload = result.to_dict()

    assert (
        payload["reason"]
        == "scheduler_disabled"
    )

    assert payload["processed"] == 0
    assert payload["succeeded"] is False

    assert (
        payload["metadata"]
        ["execution_enabled"]
        is False
    )

    assert (
        payload["metadata"]
        ["scheduler_loop_enabled"]
        is False
    )


def test_ensure_default_is_idempotent(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    scheduler_store = (
        ExecutionRecoverySchedulerStore(
            database
        )
    )

    # RecoveryService requires its dependency schemas, so use a
    # minimal stand-in for this isolated helper test.
    class NoopRecoveryService:
        def recover_stale_workers(
            self,
            *,
            limit: int,
        ):
            return []

    service = (
        ExecutionRecoverySchedulerService(
            database,
            scheduler_store=
                scheduler_store,
            recovery_service=
                NoopRecoveryService(),
        )
    )

    first = service.ensure_default()
    second = service.ensure_default()

    assert (
        first.scheduler_id
        == second.scheduler_id
    )

    assert len(
        scheduler_store.events()
    ) == 1
