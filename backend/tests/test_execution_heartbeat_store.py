from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import sqlite3

import pytest

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
)
from app.models.execution_heartbeat import (
    WorkerHeartbeatOwnerMismatch,
    WorkerHeartbeatStatus,
    WorkerHeartbeatVersionConflict,
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
            "approve-heartbeat-store-001"
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


def test_schema_is_created(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    database = environment[
        "database"
    ]

    with sqlite3.connect(
        database
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
        "execution_heartbeats"
        in tables
    )

    assert (
        "execution_heartbeat_events"
        in tables
    )


def test_register_worker(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    heartbeat = (
        environment[
            "heartbeat_store"
        ].register_worker(
            worker_id="worker:1",
            lease_id=(
                environment[
                    "lease"
                ].lease_id
            ),
        )
    )

    assert heartbeat.worker_id == "worker:1"

    assert (
        heartbeat.lease_id
        == environment["lease"].lease_id
    )

    assert (
        heartbeat.status
        == WorkerHeartbeatStatus.HEALTHY
    )

    assert heartbeat.heartbeat_version == 1

    assert (
        heartbeat.metadata[
            "execution_enabled"
        ]
        is False
    )


def test_owner_mismatch_rejected(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    with pytest.raises(
        WorkerHeartbeatOwnerMismatch,
    ):
        environment[
            "heartbeat_store"
        ].register_worker(
            worker_id="worker:2",
            lease_id=(
                environment[
                    "lease"
                ].lease_id
            ),
        )


def test_duplicate_registration_rejected(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    lease_id = environment[
        "lease"
    ].lease_id

    store.register_worker(
        worker_id="worker:1",
        lease_id=lease_id,
    )

    with pytest.raises(
        ValueError,
        match="already",
    ):
        store.register_worker(
            worker_id="worker:1",
            lease_id=lease_id,
        )


def test_record_heartbeat_advances_version(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    updated = store.record_heartbeat(
        heartbeat.worker_id,
        expected_version=1,
    )

    assert updated.heartbeat_version == 2

    assert (
        updated.status
        == WorkerHeartbeatStatus.HEALTHY
    )

    assert (
        updated.last_heartbeat_at
        >= heartbeat.last_heartbeat_at
    )


def test_stale_version_rejected(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    store.record_heartbeat(
        heartbeat.worker_id,
        expected_version=1,
    )

    with pytest.raises(
        WorkerHeartbeatVersionConflict,
    ) as exc:
        store.record_heartbeat(
            heartbeat.worker_id,
            expected_version=1,
        )

    assert exc.value.actual_version == 2


def test_stop_worker(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    stopped = store.stop_worker(
        heartbeat.worker_id,
        expected_version=1,
        reason="Worker shutdown",
    )

    assert (
        stopped.status
        == WorkerHeartbeatStatus.STOPPED
    )

    assert stopped.heartbeat_version == 2
    assert stopped.stopped_at is not None
    assert stopped.can_heartbeat is False


def test_stopped_worker_rejects_heartbeat(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    stopped = store.stop_worker(
        heartbeat.worker_id,
        expected_version=1,
    )

    with pytest.raises(
        ValueError,
        match="Stopped",
    ):
        store.record_heartbeat(
            stopped.worker_id,
            expected_version=2,
        )


def test_get_by_lease(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    loaded = store.get_by_lease(
        heartbeat.lease_id
    )

    assert loaded is not None

    assert (
        loaded.worker_id
        == heartbeat.worker_id
    )


def test_list_workers(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    records = store.list_workers(
        authorization_id=(
            environment[
                "authorization"
            ].authorization_id
        ),
        limit=100,
        offset=0,
    )

    assert len(records) == 1
    assert records[0].worker_id == "worker:1"


def test_stale_workers(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
        heartbeat_interval_seconds=5,
        heartbeat_timeout_seconds=10,
    )

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
                heartbeat.worker_id,
            ),
        )

        connection.commit()

    stale = store.stale_workers()

    assert len(stale) == 1

    assert (
        stale[0].worker_id
        == heartbeat.worker_id
    )

    assert (
        stale[0].effective_status()
        == WorkerHeartbeatStatus.STALE
    )


def test_stopped_worker_not_reported_stale(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
        heartbeat_interval_seconds=5,
        heartbeat_timeout_seconds=10,
    )

    store.stop_worker(
        heartbeat.worker_id,
        expected_version=1,
    )

    assert store.stale_workers() == []


def test_event_history(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    updated = store.record_heartbeat(
        heartbeat.worker_id,
        expected_version=1,
    )

    store.stop_worker(
        updated.worker_id,
        expected_version=2,
        reason="Finished",
    )

    assert [
        event["event_type"]
        for event in store.events(
            heartbeat.worker_id
        )
    ] == [
        "registered",
        "heartbeat",
        "stopped",
    ]


def test_expired_lease_rejects_heartbeat(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    store = environment[
        "heartbeat_store"
    ]

    heartbeat = store.register_worker(
        worker_id="worker:1",
        lease_id=(
            environment[
                "lease"
            ].lease_id
        ),
    )

    expired_time = (
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
            UPDATE execution_leases
            SET
                acquired_at = ?,
                expires_at = ?
            WHERE lease_id = ?
            """,
            (
                (
                    expired_time
                    - timedelta(seconds=60)
                ).isoformat(),
                expired_time.isoformat(),
                environment[
                    "lease"
                ].lease_id,
            ),
        )

        connection.commit()

    with pytest.raises(
        ValueError,
        match="lease is not active",
    ):
        store.record_heartbeat(
            heartbeat.worker_id,
            expected_version=1,
        )
