from __future__ import annotations

import asyncio
import sqlite3

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from fastapi import HTTPException

from app.api.v1 import (
    execution_recovery_scheduler,
)
from app.api.v1.router import (
    api_router,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
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
from app.services.execution_recovery_scheduler_store import (
    ExecutionRecoverySchedulerStore,
)
from tests.test_execution_simulator import (
    make_plan,
)


def run(coroutine):
    return asyncio.run(
        coroutine
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


@pytest.fixture
def scheduler_environment(
    tmp_path,
    monkeypatch,
):
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    monkeypatch.setenv(
        "SS4TS_EXECUTION_AUTH_DB",
        str(database),
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

    ExecutionRecoveryService(
        database
    )

    scheduler_store = (
        ExecutionRecoverySchedulerStore(
            database
        )
    )

    scheduler = scheduler_store.create_default(
        interval_seconds=60,
        batch_size=100,
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
            "approve-scheduler-api-001"
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

    return {
        "database":
            database,
        "authorization_store":
            authorization_store,
        "lease_store":
            lease_store,
        "heartbeat_store":
            heartbeat_store,
        "scheduler_store":
            scheduler_store,
        "scheduler":
            scheduler,
        "authorization":
            authorization,
        "lease":
            lease,
        "heartbeat":
            heartbeat,
    }


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


def test_get_creates_default(
    scheduler_environment,
) -> None:
    result = run(
        execution_recovery_scheduler
        .get_execution_recovery_scheduler()
    )

    assert (
        result["scheduler_id"]
        == "recovery-scheduler:default"
    )

    assert result["enabled"] is False

    assert (
        result["safety"]
        ["background_loop_enabled"]
        is False
    )


def test_enable_scheduler(
    scheduler_environment,
) -> None:
    result = run(
        execution_recovery_scheduler
        .enable_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerVersionPayload(
                    expected_version=1
                )
            )
        )
    )

    assert result["enabled"] is True
    assert result["status"] == "idle"
    assert result["scheduler_version"] == 2


def test_enable_conflict_returns_409(
    scheduler_environment,
) -> None:
    run(
        execution_recovery_scheduler
        .enable_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerVersionPayload(
                    expected_version=1
                )
            )
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_recovery_scheduler
            .enable_execution_recovery_scheduler(
                (
                    execution_recovery_scheduler
                    .SchedulerVersionPayload(
                        expected_version=2
                    )
                )
            )
        )

    assert exc.value.status_code == 409


def test_version_conflict_returns_409(
    scheduler_environment,
) -> None:
    run(
        execution_recovery_scheduler
        .enable_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerVersionPayload(
                    expected_version=1
                )
            )
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_recovery_scheduler
            .disable_execution_recovery_scheduler(
                (
                    execution_recovery_scheduler
                    .SchedulerVersionPayload(
                        expected_version=1
                    )
                )
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "scheduler_version_conflict"
    )


def test_update_configuration(
    scheduler_environment,
) -> None:
    result = run(
        execution_recovery_scheduler
        .update_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerConfigurationPayload(
                    expected_version=1,
                    interval_seconds=120,
                    batch_size=50,
                )
            )
        )
    )

    assert result["interval_seconds"] == 120
    assert result["batch_size"] == 50
    assert result["scheduler_version"] == 2


def test_configuration_requires_change(
    scheduler_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_recovery_scheduler
            .update_execution_recovery_scheduler(
                (
                    execution_recovery_scheduler
                    .SchedulerConfigurationPayload(
                        expected_version=1,
                    )
                )
            )
        )

    assert exc.value.status_code == 422


def test_manual_run_disabled_scheduler(
    scheduler_environment,
) -> None:
    result = run(
        execution_recovery_scheduler
        .run_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerRunPayload(
                    force=True
                )
            )
        )
    )

    assert result["executed"] is False

    assert (
        result["reason"]
        == "scheduler_disabled"
    )


def test_manual_run_recovers_stale_worker(
    scheduler_environment,
) -> None:
    run(
        execution_recovery_scheduler
        .enable_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerVersionPayload(
                    expected_version=1
                )
            )
        )
    )

    make_worker_stale(
        scheduler_environment
    )

    result = run(
        execution_recovery_scheduler
        .run_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerRunPayload(
                    force=True
                )
            )
        )
    )

    assert result["executed"] is True
    assert result["reason"] == "run_completed"
    assert result["recovered"] == 1

    assert (
        result["safety"]
        ["manual_run_only"]
        is True
    )


def test_scheduler_events(
    scheduler_environment,
) -> None:
    run(
        execution_recovery_scheduler
        .enable_execution_recovery_scheduler(
            (
                execution_recovery_scheduler
                .SchedulerVersionPayload(
                    expected_version=1
                )
            )
        )
    )

    result = run(
        execution_recovery_scheduler
        .execution_recovery_scheduler_events()
    )

    assert [
        event["event_type"]
        for event in result["events"]
    ] == [
        "created",
        "enabled",
    ]


def test_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/"
            "execution-recovery-scheduler"
        ),
        (
            "/api/v1/"
            "execution-recovery-scheduler/"
            "enable"
        ),
        (
            "/api/v1/"
            "execution-recovery-scheduler/"
            "disable"
        ),
        (
            "/api/v1/"
            "execution-recovery-scheduler/"
            "configuration"
        ),
        (
            "/api/v1/"
            "execution-recovery-scheduler/"
            "run"
        ),
        (
            "/api/v1/"
            "execution-recovery-scheduler/"
            "events"
        ),
    }

    assert expected.issubset(
        paths
    )
