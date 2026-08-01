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
from app.models.execution_lease import (
    ExecutionLeaseStatus,
    LeaseConflict,
    LeaseTokenMismatch,
    LeaseVersionConflict,
)
from app.services.execution_authorization import (
    build_execution_authorization,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
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

    return (
        database,
        authorization_store,
        lease_store,
    )


def create_pending(
    authorization_store:
        ExecutionAuthorizationStore,
):
    return authorization_store.create(
        build_execution_authorization(
            make_plan(),
            requester=requester(),
        )
    )


def create_approved(
    authorization_store:
        ExecutionAuthorizationStore,
):
    authorization = create_pending(
        authorization_store
    )

    approved = (
        authorization_store
        .approve_atomic(
            authorization.authorization_id,
            approver=senior(),
            expected_version=1,
            idempotency_key=(
                "approve-for-lease-"
                + authorization.authorization_id
            ),
        )
    )

    loaded = authorization_store.get(
        approved.authorization_id
    )

    assert loaded is not None

    return loaded


def test_schema_is_created(
    tmp_path,
) -> None:
    database, _, _ = make_environment(
        tmp_path
    )

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

    assert "execution_leases" in tables
    assert "execution_lease_events" in tables


def test_pending_authorization_cannot_acquire(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_pending(
        authorization_store
    )

    with pytest.raises(
        ValueError,
        match="not usable",
    ):
        lease_store.acquire(
            authorization.authorization_id,
            owner_id="worker:1",
        )


def test_approved_authorization_can_acquire(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
        ttl_seconds=60,
    )

    assert lease.is_active is True
    assert lease.lease_version == 1

    assert (
        lease.authorization_id
        == authorization.authorization_id
    )

    assert (
        lease.metadata[
            "execution_enabled"
        ]
        is False
    )


def test_single_active_lease_enforced(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    with pytest.raises(
        LeaseConflict,
    ) as exc:
        lease_store.acquire(
            authorization.authorization_id,
            owner_id="worker:2",
        )

    assert exc.value.owner_id == "worker:1"


def test_verify_token(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    assert lease_store.verify_token(
        lease.lease_id,
        lease_token=
            lease.lease_token,
    ) is True

    assert lease_store.verify_token(
        lease.lease_id,
        lease_token="wrong-token",
    ) is False


def test_renew_increments_version(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    renewed = lease_store.renew(
        lease.lease_id,
        lease_token=
            lease.lease_token,
        expected_version=1,
        ttl_seconds=120,
    )

    assert renewed.lease_version == 2
    assert renewed.renewed_at is not None
    assert renewed.is_active is True


def test_renew_rejects_wrong_token(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    with pytest.raises(
        LeaseTokenMismatch,
    ):
        lease_store.renew(
            lease.lease_id,
            lease_token="wrong-token",
            expected_version=1,
        )


def test_renew_rejects_stale_version(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    renewed = lease_store.renew(
        lease.lease_id,
        lease_token=
            lease.lease_token,
        expected_version=1,
    )

    with pytest.raises(
        LeaseVersionConflict,
    ) as exc:
        lease_store.renew(
            renewed.lease_id,
            lease_token=
                renewed.lease_token,
            expected_version=1,
        )

    assert exc.value.actual_version == 2


def test_release_increments_version(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    released = lease_store.release(
        lease.lease_id,
        lease_token=
            lease.lease_token,
        expected_version=1,
    )

    assert (
        released.status
        == ExecutionLeaseStatus.RELEASED
    )

    assert released.lease_version == 2
    assert released.released_at is not None
    assert released.is_active is False


def test_release_twice_is_rejected(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    released = lease_store.release(
        lease.lease_id,
        lease_token=
            lease.lease_token,
        expected_version=1,
    )

    with pytest.raises(
        ValueError,
        match="active",
    ):
        lease_store.release(
            released.lease_id,
            lease_token=
                released.lease_token,
            expected_version=2,
        )


def test_released_lease_allows_new_acquire(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    first = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    lease_store.release(
        first.lease_id,
        lease_token=
            first.lease_token,
        expected_version=1,
    )

    second = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:2",
    )

    assert second.is_active is True
    assert second.owner_id == "worker:2"
    assert second.lease_id != first.lease_id


def test_expire_due(
    tmp_path,
) -> None:
    database, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    now = datetime.now(
        timezone.utc
    )

    acquired_time = (
        now
        - timedelta(seconds=120)
    )

    expired_time = (
        now
        - timedelta(seconds=1)
    )

    with sqlite3.connect(
        database
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
                acquired_time.isoformat(),
                expired_time.isoformat(),
                lease.lease_id,
            ),
        )

        connection.commit()

    assert lease_store.expire_due() == 1

    loaded = lease_store.get(
        lease.lease_id
    )

    assert loaded is not None

    assert (
        loaded.status
        == ExecutionLeaseStatus.EXPIRED
    )

    assert loaded.lease_version == 2


def test_expired_lease_allows_new_acquire(
    tmp_path,
) -> None:
    database, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    first = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    now = datetime.now(
        timezone.utc
    )

    acquired_time = (
        now
        - timedelta(seconds=120)
    )

    expired_time = (
        now
        - timedelta(seconds=1)
    )

    with sqlite3.connect(
        database
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
                acquired_time.isoformat(),
                expired_time.isoformat(),
                first.lease_id,
            ),
        )

        connection.commit()

    second = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:2",
    )

    assert second.owner_id == "worker:2"
    assert second.is_active is True

    old = lease_store.get(
        first.lease_id
    )

    assert old is not None

    assert (
        old.status
        == ExecutionLeaseStatus.EXPIRED
    )


def test_event_history(
    tmp_path,
) -> None:
    _, authorization_store, lease_store = (
        make_environment(
            tmp_path
        )
    )

    authorization = create_approved(
        authorization_store
    )

    lease = lease_store.acquire(
        authorization.authorization_id,
        owner_id="worker:1",
    )

    renewed = lease_store.renew(
        lease.lease_id,
        lease_token=
            lease.lease_token,
        expected_version=1,
    )

    lease_store.release(
        renewed.lease_id,
        lease_token=
            renewed.lease_token,
        expected_version=2,
    )

    assert [
        event["event_type"]
        for event in lease_store.events(
            lease.lease_id
        )
    ] == [
        "acquired",
        "renewed",
        "released",
    ]
