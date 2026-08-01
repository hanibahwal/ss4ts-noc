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
from app.models.execution_heartbeat import (
    WorkerHeartbeatStatus,
)
from app.models.execution_lease import (
    ExecutionLeaseStatus,
)
from app.models.execution_recovery import (
    RecoveryDecision,
    RecoveryReason,
    RecoveryStatus,
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
            "approve-recovery-service-001"
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


def test_schema_is_created(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    with sqlite3.connect(
        environment["database"]
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

    assert "execution_recoveries" in tables

    assert (
        "execution_recovery_events"
        in tables
    )


def test_stale_worker_revokes_active_lease(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    recovery = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    assert (
        recovery.status
        == RecoveryStatus.RECOVERED
    )

    assert (
        recovery.decision
        == RecoveryDecision.REVOKE_LEASE
    )

    assert (
        recovery.reason
        == RecoveryReason.WORKER_STALE
    )

    assert recovery.succeeded is True
    assert recovery.lease_version_advanced
    assert recovery.heartbeat_version_advanced


def test_recovery_updates_lease_and_heartbeat(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    recovery = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    lease = environment[
        "lease_store"
    ].get(
        recovery.lease_id
    )

    heartbeat = environment[
        "heartbeat_store"
    ].get(
        recovery.worker_id
    )

    assert lease is not None
    assert heartbeat is not None

    assert (
        lease.status
        == ExecutionLeaseStatus.REVOKED
    )

    assert lease.lease_version == 2

    assert (
        heartbeat.status
        == WorkerHeartbeatStatus.STALE
    )

    assert heartbeat.heartbeat_version == 2


def test_fresh_worker_is_skipped(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    recovery = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    assert (
        recovery.status
        == RecoveryStatus.SKIPPED
    )

    assert (
        recovery.decision
        == RecoveryDecision.NO_ACTION
    )

    lease = environment[
        "lease_store"
    ].get(
        environment["lease"].lease_id
    )

    assert lease is not None

    assert (
        lease.status
        == ExecutionLeaseStatus.ACTIVE
    )


def test_expired_lease_is_expired_by_recovery(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    expired_at = (
        datetime.now(
            timezone.utc
        )
        - timedelta(seconds=1)
    )

    acquired_at = (
        expired_at
        - timedelta(seconds=60)
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
                acquired_at.isoformat(),
                expired_at.isoformat(),
                environment["lease"].lease_id,
            ),
        )

        connection.commit()

    recovery = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    assert (
        recovery.status
        == RecoveryStatus.RECOVERED
    )

    assert (
        recovery.decision
        == RecoveryDecision.EXPIRE_LEASE
    )

    assert (
        recovery.reason
        == RecoveryReason.LEASE_EXPIRED
    )

    lease = environment[
        "lease_store"
    ].get(
        environment["lease"].lease_id
    )

    assert lease is not None

    assert (
        lease.status
        == ExecutionLeaseStatus.EXPIRED
    )


def test_recovery_is_idempotent(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    first = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    second = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    assert (
        second.recovery_id
        == first.recovery_id
    )

    assert (
        len(
            environment[
                "recovery_service"
            ].list_recoveries()
        )
        == 1
    )


def test_recover_stale_workers(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    results = (
        environment[
            "recovery_service"
        ].recover_stale_workers()
    )

    assert len(results) == 1

    assert (
        results[0].status
        == RecoveryStatus.RECOVERED
    )


def test_recovery_events(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    recovery = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    event_types = [
        event["event_type"]
        for event in (
            environment[
                "recovery_service"
            ].events(
                recovery.recovery_id
            )
        )
    ]

    assert event_types == [
        "recovered",
        "heartbeat_stale",
        "lease_revoked",
    ]


def test_recovered_lease_allows_new_acquire(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    environment[
        "recovery_service"
    ].recover_worker(
        "worker:1"
    )

    second = environment[
        "lease_store"
    ].acquire(
        environment[
            "authorization"
        ].authorization_id,
        owner_id="worker:2",
        ttl_seconds=60,
    )

    assert second.is_active is True
    assert second.owner_id == "worker:2"


def test_safety_metadata(
    tmp_path,
) -> None:
    environment = make_environment(
        tmp_path
    )

    make_worker_stale(
        environment
    )

    recovery = (
        environment[
            "recovery_service"
        ].recover_worker(
            "worker:1"
        )
    )

    assert (
        recovery.metadata[
            "execution_enabled"
        ]
        is False
    )

    assert (
        recovery.metadata[
            "network_io_performed"
        ]
        is False
    )

    assert (
        recovery.metadata[
            "device_command_executed"
        ]
        is False
    )
