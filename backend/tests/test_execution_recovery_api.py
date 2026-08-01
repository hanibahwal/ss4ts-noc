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
    execution_recovery,
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
def recovery_environment(
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

    recovery_service = (
        ExecutionRecoveryService(
            database
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
            "approve-recovery-api-001"
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
        "recovery_service":
            recovery_service,
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


def test_recover_worker(
    recovery_environment,
) -> None:
    make_worker_stale(
        recovery_environment
    )

    result = run(
        execution_recovery
        .recover_execution_worker(
            "worker:1"
        )
    )

    assert result["status"] == "recovered"

    assert (
        result["decision"]
        == "revoke_lease"
    )

    assert (
        result["reason"]
        == "worker_stale"
    )

    assert result["succeeded"] is True

    assert (
        result["safety"]
        ["execution_enabled"]
        is False
    )


def test_fresh_worker_is_skipped(
    recovery_environment,
) -> None:
    result = run(
        execution_recovery
        .recover_execution_worker(
            "worker:1"
        )
    )

    assert result["status"] == "skipped"
    assert result["decision"] == "no_action"
    assert result["succeeded"] is False


def test_missing_worker_returns_404(
    recovery_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_recovery
            .recover_execution_worker(
                "worker:missing"
            )
        )

    assert exc.value.status_code == 404


def test_run_recovers_stale_workers(
    recovery_environment,
) -> None:
    make_worker_stale(
        recovery_environment
    )

    result = run(
        execution_recovery
        .run_stale_recovery(
            execution_recovery
            .RunRecoveryPayload(
                limit=100
            )
        )
    )

    assert result["count"] == 1
    assert result["recovered_count"] == 1
    assert result["skipped_count"] == 0

    assert (
        result["records"][0]["status"]
        == "recovered"
    )

    assert (
        result["safety"]
        ["scheduler_enabled"]
        is False
    )


def test_run_with_no_stale_workers(
    recovery_environment,
) -> None:
    result = run(
        execution_recovery
        .run_stale_recovery(
            execution_recovery
            .RunRecoveryPayload(
                limit=100
            )
        )
    )

    assert result["count"] == 0
    assert result["recovered_count"] == 0
    assert result["records"] == []


def test_list_recoveries(
    recovery_environment,
) -> None:
    make_worker_stale(
        recovery_environment
    )

    run(
        execution_recovery
        .recover_execution_worker(
            "worker:1"
        )
    )

    result = run(
        execution_recovery
        .list_execution_recoveries(
            status=None,
            limit=100,
            offset=0,
        )
    )

    assert result["count"] == 1

    assert (
        result["records"][0]["worker_id"]
        == "worker:1"
    )


def test_get_recovery(
    recovery_environment,
) -> None:
    make_worker_stale(
        recovery_environment
    )

    created = run(
        execution_recovery
        .recover_execution_worker(
            "worker:1"
        )
    )

    loaded = run(
        execution_recovery
        .get_execution_recovery(
            created["recovery_id"]
        )
    )

    assert (
        loaded["recovery_id"]
        == created["recovery_id"]
    )

    assert loaded["status"] == "recovered"


def test_missing_recovery_returns_404(
    recovery_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_recovery
            .get_execution_recovery(
                "recovery:missing"
            )
        )

    assert exc.value.status_code == 404


def test_recovery_events(
    recovery_environment,
) -> None:
    make_worker_stale(
        recovery_environment
    )

    created = run(
        execution_recovery
        .recover_execution_worker(
            "worker:1"
        )
    )

    result = run(
        execution_recovery
        .execution_recovery_events(
            created["recovery_id"]
        )
    )

    assert result["count"] == 3

    assert [
        event["event_type"]
        for event in result["events"]
    ] == [
        "recovered",
        "heartbeat_stale",
        "lease_revoked",
    ]


def test_recovery_is_idempotent(
    recovery_environment,
) -> None:
    make_worker_stale(
        recovery_environment
    )

    first = run(
        execution_recovery
        .recover_execution_worker(
            "worker:1"
        )
    )

    second = run(
        execution_recovery
        .recover_execution_worker(
            "worker:1"
        )
    )

    assert (
        second["recovery_id"]
        == first["recovery_id"]
    )


def test_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/"
            "execution-recovery/run"
        ),
        (
            "/api/v1/"
            "execution-recovery/workers/"
            "{worker_id}"
        ),
        "/api/v1/execution-recovery",
        (
            "/api/v1/"
            "execution-recovery/"
            "{recovery_id}"
        ),
        (
            "/api/v1/"
            "execution-recovery/"
            "{recovery_id}/events"
        ),
    }

    assert expected.issubset(
        paths
    )
