from __future__ import annotations

import sqlite3

from dataclasses import replace
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationStatus,
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


def senior() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:senior",
        display_name="Senior Engineer",
        role=ApprovalRole.SENIOR_ENGINEER,
    )


def engineer() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:engineer",
        display_name="Engineer",
        role=ApprovalRole.NETWORK_ENGINEER,
    )


def make_authorization():
    return build_execution_authorization(
        make_plan(),
        requester=requester(),
    )


def test_create_and_get(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    created = store.create(
        make_authorization()
    )

    loaded = store.get(
        created.authorization_id
    )

    assert loaded is not None

    assert (
        loaded.authorization_id
        == created.authorization_id
    )

    assert (
        loaded.status
        == AuthorizationStatus.PENDING
    )


def test_checksum_verifies(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    assert store.verify(
        authorization.authorization_id
    ) is True


def test_tampering_is_detected(
    tmp_path,
) -> None:
    database = (
        tmp_path / "authorization.db"
    )

    store = ExecutionAuthorizationStore(
        database
    )

    authorization = store.create(
        make_authorization()
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE execution_authorizations
            SET status = 'approved'
            WHERE authorization_id = ?
            """,
            (
                authorization
                .authorization_id,
            ),
        )

        connection.commit()

    assert store.verify(
        authorization.authorization_id
    ) is False


def test_duplicate_is_rejected(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = (
        make_authorization()
    )

    store.create(
        authorization
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        store.create(
            authorization
        )


def test_list_and_count(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    store.create(
        make_authorization()
    )

    assert store.count() == 1

    records = store.list_authorizations(
        status=AuthorizationStatus.PENDING
    )

    assert len(records) == 1


def test_insufficient_role_cannot_approve(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    with pytest.raises(
        PermissionError,
        match="insufficient",
    ):
        store.approve(
            authorization.authorization_id,
            approver=engineer(),
        )


def test_senior_can_approve(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    approved = store.approve(
        authorization.authorization_id,
        approver=senior(),
    )

    assert (
        approved.status
        == AuthorizationStatus.APPROVED
    )

    assert approved.is_usable is True
    assert approved.execution_allowed is True

    assert store.verify(
        approved.authorization_id
    ) is True


def test_reject_pending_authorization(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    rejected = store.reject(
        authorization.authorization_id,
        approver=senior(),
        reason="Maintenance window unavailable",
    )

    assert (
        rejected.status
        == AuthorizationStatus.REJECTED
    )

    assert rejected.rejection_reason


def test_revoke_approved_authorization(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    approved = store.approve(
        authorization.authorization_id,
        approver=senior(),
    )

    revoked = store.revoke(
        approved.authorization_id,
        actor=senior(),
        reason="Network conditions changed",
    )

    assert (
        revoked.status
        == AuthorizationStatus.REVOKED
    )

    assert revoked.is_usable is False
    assert revoked.revocation_reason


def test_consume_authorization_once(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    approved = store.approve(
        authorization.authorization_id,
        approver=senior(),
    )

    consumed = store.consume(
        approved.authorization_id
    )

    assert (
        consumed.status
        == AuthorizationStatus.USED
    )

    assert consumed.consumed is True
    assert consumed.is_usable is False

    with pytest.raises(
        ValueError,
        match="not usable",
    ):
        store.consume(
            approved.authorization_id
        )


def test_expired_cannot_be_approved(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = replace(
        make_authorization(),
        expires_at=(
            datetime.now(
                timezone.utc
            )
            - timedelta(minutes=1)
        ),
    )

    store.create(
        authorization
    )

    with pytest.raises(
        ValueError,
        match="expired",
    ):
        store.approve(
            authorization.authorization_id,
            approver=senior(),
        )

    loaded = store.get(
        authorization.authorization_id
    )

    assert loaded is not None

    assert (
        loaded.status
        == AuthorizationStatus.EXPIRED
    )


def test_expire_due(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = replace(
        make_authorization(),
        expires_at=(
            datetime.now(
                timezone.utc
            )
            - timedelta(seconds=1)
        ),
    )

    store.create(
        authorization
    )

    assert store.expire_due() == 1

    loaded = store.get(
        authorization.authorization_id
    )

    assert loaded is not None

    assert (
        loaded.status
        == AuthorizationStatus.EXPIRED
    )


def test_event_history(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    store.approve(
        authorization.authorization_id,
        approver=senior(),
    )

    events = store.events(
        authorization.authorization_id
    )

    assert [
        event["event_type"]
        for event in events
    ] == [
        "created",
        "approved",
    ]


def test_store_never_enables_device_execution(
    tmp_path,
) -> None:
    store = ExecutionAuthorizationStore(
        tmp_path / "authorization.db"
    )

    authorization = store.create(
        make_authorization()
    )

    approved = store.approve(
        authorization.authorization_id,
        approver=senior(),
    )

    assert (
        approved.metadata
        ["execution_enabled"]
        is False
    )

    assert (
        approved.metadata
        ["network_io_performed"]
        is False
    )

    assert (
        approved.metadata
        ["device_command_executed"]
        is False
    )
