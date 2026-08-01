from __future__ import annotations

import sqlite3

import pytest

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationStatus,
)
from app.models.execution_concurrency import (
    AuthorizationVersionConflict,
    IdempotencyConflict,
    IdempotencyDisposition,
)
from app.services.execution_authorization import (
    build_execution_authorization,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
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


def senior(
    *,
    identity_id: str = "user:senior",
) -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id=identity_id,
        display_name="Senior Engineer",
        role=ApprovalRole.SENIOR_ENGINEER,
    )


def make_store(
    tmp_path,
) -> ExecutionAuthorizationStore:
    return ExecutionAuthorizationStore(
        tmp_path
        / "execution-authorization.db"
    )


def create_pending(
    store: ExecutionAuthorizationStore,
):
    return store.create(
        build_execution_authorization(
            make_plan(),
            requester=requester(),
        )
    )


def test_schema_has_record_version(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    ExecutionAuthorizationStore(
        database
    )

    with sqlite3.connect(
        database
    ) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    execution_authorizations
                )
                """
            ).fetchall()
        }

    assert "record_version" in columns


def test_new_record_starts_at_version_one(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    authorization = create_pending(
        store
    )

    assert (
        store.get_record_version(
            authorization.authorization_id
        )
        == 1
    )


def test_atomic_approval_advances_version(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    authorization = create_pending(
        store
    )

    result = store.approve_atomic(
        authorization.authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=
            "approve-atomic-001",
    )

    assert (
        result.disposition
        == IdempotencyDisposition.NEW
    )

    assert result.previous_version == 1
    assert result.current_version == 2
    assert result.version_advanced is True

    assert (
        store.get_record_version(
            authorization.authorization_id
        )
        == 2
    )

    loaded = store.get(
        authorization.authorization_id
    )

    assert loaded is not None

    assert (
        loaded.status
        == AuthorizationStatus.APPROVED
    )

    assert store.verify(
        authorization.authorization_id
    ) is True


def test_same_request_is_replayed(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    authorization = create_pending(
        store
    )

    first = store.approve_atomic(
        authorization.authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=
            "approve-replay-001",
    )

    replay = store.approve_atomic(
        authorization.authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=
            "approve-replay-001",
    )

    assert (
        first.disposition
        == IdempotencyDisposition.NEW
    )

    assert (
        replay.disposition
        == IdempotencyDisposition.REPLAY
    )

    assert replay.replayed is True
    assert replay.current_version == 2

    assert (
        replay.response_payload
        == first.response_payload
    )

    events = store.events(
        authorization.authorization_id
    )

    assert [
        item["event_type"]
        for item in events
    ] == [
        "created",
        "approved",
    ]


def test_same_key_different_request_conflicts(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    authorization = create_pending(
        store
    )

    store.approve_atomic(
        authorization.authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=
            "approve-conflict-001",
    )

    with pytest.raises(
        IdempotencyConflict,
    ):
        store.approve_atomic(
            authorization.authorization_id,
            approver=senior(
                identity_id="user:other"
            ),
            expected_version=1,
            idempotency_key=
                "approve-conflict-001",
        )


def test_stale_version_conflicts(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    authorization = create_pending(
        store
    )

    store.approve_atomic(
        authorization.authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=
            "approve-version-001",
    )

    with pytest.raises(
        AuthorizationVersionConflict,
    ) as exc:
        store.approve_atomic(
            authorization.authorization_id,
            approver=senior(),
            expected_version=1,
            idempotency_key=
                "approve-version-002",
        )

    assert (
        exc.value.expected_version
        == 1
    )

    assert (
        exc.value.actual_version
        == 2
    )


def test_insufficient_role_does_not_mutate(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    authorization = create_pending(
        store
    )

    engineer = ApprovalIdentity(
        identity_id="user:engineer",
        display_name="Engineer",
        role=ApprovalRole.NETWORK_ENGINEER,
    )

    with pytest.raises(
        PermissionError,
        match="insufficient",
    ):
        store.approve_atomic(
            authorization.authorization_id,
            approver=engineer,
            expected_version=1,
            idempotency_key=
                "approve-role-001",
        )

    assert (
        store.get_record_version(
            authorization.authorization_id
        )
        == 1
    )

    loaded = store.get(
        authorization.authorization_id
    )

    assert loaded is not None

    assert (
        loaded.status
        == AuthorizationStatus.PENDING
    )
