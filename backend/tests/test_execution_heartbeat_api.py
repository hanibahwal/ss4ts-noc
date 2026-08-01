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
    execution_heartbeats,
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
def heartbeat_environment(
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
            "approve-heartbeat-api-001"
        ),
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
        ttl_seconds=300,
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
        "authorization":
            authorization,
        "lease":
            lease,
    }


def register_payload(
    *,
    worker_id: str = "worker:1",
):
    return (
        execution_heartbeats
        .RegisterHeartbeatPayload(
            worker_id=worker_id,
            heartbeat_interval_seconds=15,
            heartbeat_timeout_seconds=45,
            metadata={
                "source": "api-test",
            },
        )
    )


def test_register_worker(
    heartbeat_environment,
) -> None:
    result = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    assert result["worker_id"] == "worker:1"
    assert result["status"] == "healthy"
    assert result["heartbeat_version"] == 1

    assert (
        result["metadata"]["source"]
        == "api-test"
    )

    assert (
        result["safety"]
        ["execution_enabled"]
        is False
    )


def test_owner_mismatch_returns_403(
    heartbeat_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_heartbeats
            .register_execution_worker(
                heartbeat_environment[
                    "lease"
                ].lease_id,
                register_payload(
                    worker_id="worker:2"
                ),
            )
        )

    assert exc.value.status_code == 403

    assert (
        exc.value.detail["type"]
        == "heartbeat_owner_mismatch"
    )


def test_missing_lease_returns_404(
    heartbeat_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_heartbeats
            .register_execution_worker(
                "lease:missing",
                register_payload(),
            )
        )

    assert exc.value.status_code == 404


def test_record_heartbeat(
    heartbeat_environment,
) -> None:
    registered = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    updated = run(
        execution_heartbeats
        .record_execution_worker_heartbeat(
            registered["worker_id"],
            (
                execution_heartbeats
                .RecordHeartbeatPayload(
                    expected_version=1,
                )
            ),
        )
    )

    assert updated["heartbeat_version"] == 2
    assert updated["status"] == "healthy"


def test_stale_version_returns_409(
    heartbeat_environment,
) -> None:
    registered = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    run(
        execution_heartbeats
        .record_execution_worker_heartbeat(
            registered["worker_id"],
            (
                execution_heartbeats
                .RecordHeartbeatPayload(
                    expected_version=1,
                )
            ),
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_heartbeats
            .record_execution_worker_heartbeat(
                registered["worker_id"],
                (
                    execution_heartbeats
                    .RecordHeartbeatPayload(
                        expected_version=1,
                    )
                ),
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "heartbeat_version_conflict"
    )

    assert (
        exc.value.detail["actual_version"]
        == 2
    )


def test_stop_worker(
    heartbeat_environment,
) -> None:
    registered = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    stopped = run(
        execution_heartbeats
        .stop_execution_worker(
            registered["worker_id"],
            (
                execution_heartbeats
                .StopWorkerPayload(
                    expected_version=1,
                    reason="Maintenance",
                )
            ),
        )
    )

    assert stopped["status"] == "stopped"
    assert stopped["heartbeat_version"] == 2
    assert stopped["stopped_at"] is not None
    assert stopped["can_heartbeat"] is False


def test_stopped_worker_rejects_heartbeat(
    heartbeat_environment,
) -> None:
    registered = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    run(
        execution_heartbeats
        .stop_execution_worker(
            registered["worker_id"],
            (
                execution_heartbeats
                .StopWorkerPayload(
                    expected_version=1,
                )
            ),
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_heartbeats
            .record_execution_worker_heartbeat(
                registered["worker_id"],
                (
                    execution_heartbeats
                    .RecordHeartbeatPayload(
                        expected_version=2,
                    )
                ),
            )
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "heartbeat_not_allowed"
    )


def test_get_worker(
    heartbeat_environment,
) -> None:
    registered = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    loaded = run(
        execution_heartbeats
        .get_execution_worker(
            registered["worker_id"]
        )
    )

    assert (
        loaded["worker_id"]
        == registered["worker_id"]
    )


def test_list_workers(
    heartbeat_environment,
) -> None:
    run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    result = run(
        execution_heartbeats
        .list_execution_workers(
            authorization_id=(
                heartbeat_environment[
                    "authorization"
                ].authorization_id
            ),
            lease_id=None,
            status=None,
            limit=100,
            offset=0,
        )
    )

    assert result["count"] == 1
    assert result["records"][0]["worker_id"] == "worker:1"


def test_stale_workers(
    heartbeat_environment,
) -> None:
    registered = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            (
                execution_heartbeats
                .RegisterHeartbeatPayload(
                    worker_id="worker:1",
                    heartbeat_interval_seconds=5,
                    heartbeat_timeout_seconds=10,
                )
            ),
        )
    )

    stale_time = (
        datetime.now(
            timezone.utc
        )
        - timedelta(seconds=30)
    )

    with sqlite3.connect(
        heartbeat_environment[
            "database"
        ]
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
                registered["worker_id"],
            ),
        )

        connection.commit()

    result = run(
        execution_heartbeats
        .stale_execution_workers()
    )

    assert result["count"] == 1

    assert (
        result["records"][0]
        ["effective_status"]
        == "stale"
    )


def test_worker_events(
    heartbeat_environment,
) -> None:
    registered = run(
        execution_heartbeats
        .register_execution_worker(
            heartbeat_environment[
                "lease"
            ].lease_id,
            register_payload(),
        )
    )

    updated = run(
        execution_heartbeats
        .record_execution_worker_heartbeat(
            registered["worker_id"],
            (
                execution_heartbeats
                .RecordHeartbeatPayload(
                    expected_version=1,
                )
            ),
        )
    )

    run(
        execution_heartbeats
        .stop_execution_worker(
            updated["worker_id"],
            (
                execution_heartbeats
                .StopWorkerPayload(
                    expected_version=2,
                    reason="Finished",
                )
            ),
        )
    )

    result = run(
        execution_heartbeats
        .execution_worker_events(
            registered["worker_id"]
        )
    )

    assert [
        event["event_type"]
        for event in result["events"]
    ] == [
        "registered",
        "heartbeat",
        "stopped",
    ]


def test_missing_worker_returns_404(
    heartbeat_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_heartbeats
            .get_execution_worker(
                "worker:missing"
            )
        )

    assert exc.value.status_code == 404


def test_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/execution-leases/"
            "{lease_id}/heartbeat/register"
        ),
        (
            "/api/v1/execution-workers/"
            "{worker_id}/heartbeat"
        ),
        (
            "/api/v1/execution-workers/"
            "{worker_id}/stop"
        ),
        "/api/v1/execution-workers",
        "/api/v1/execution-workers/stale",
        (
            "/api/v1/execution-workers/"
            "{worker_id}"
        ),
        (
            "/api/v1/execution-workers/"
            "{worker_id}/events"
        ),
    }

    assert expected.issubset(
        paths
    )
