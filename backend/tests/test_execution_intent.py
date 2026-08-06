from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from app.models.execution_intent import (
    ExecutionIntent,
)
from app.services import (
    remediation_approval_service,
)


def _future() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        + timedelta(minutes=30)
    ).isoformat()


def _use_database(
    tmp_path,
    monkeypatch,
) -> None:
    database = (
        tmp_path
        / "remediation-approval.db"
    )

    monkeypatch.setattr(
        remediation_approval_service,
        "DB_PATH",
        database,
    )

    remediation_approval_service._init_db()


def test_intent_fingerprint_is_deterministic(
) -> None:
    first = ExecutionIntent(
        approval_id="approval-1",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        execution_class="READ_ONLY",
        read_only=True,
        verification_required=True,
        rollback_required=False,
        expires_at=_future(),
    )

    second = ExecutionIntent(
        approval_id="approval-1",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        execution_class="READ_ONLY",
        read_only=True,
        verification_required=True,
        rollback_required=False,
        expires_at=first.expires_at,
    )

    assert (
        first.fingerprint
        == second.fingerprint
    )

    assert len(first.fingerprint) == 64


def test_intent_is_immutable() -> None:
    intent = ExecutionIntent(
        approval_id="approval-1",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        execution_class="READ_ONLY",
        read_only=True,
        verification_required=True,
        rollback_required=False,
        expires_at=_future(),
    )

    with pytest.raises(
        FrozenInstanceError
    ):
        intent.router_ip = "10.0.0.1"


def test_approval_stores_intent(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    created = (
        remediation_approval_service
        .create_approval_request(
            router_ip="192.168.88.1",
            action_type=(
                "CHECK_CPU_PROCESS"
            ),
            reason="Intent test",
        )
    )

    approval = created["approval"]
    intent = created["intent"]

    assert approval[
        "intent_fingerprint"
    ] == intent[
        "intent_fingerprint"
    ]

    assert intent[
        "execution_class"
    ] == "READ_ONLY"

    assert intent["read_only"] is True

    assert (
        intent["rollback_required"]
        is False
    )


def test_tampered_intent_is_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    created = (
        remediation_approval_service
        .create_approval_request(
            router_ip="192.168.88.1",
            action_type=(
                "CHECK_CPU_PROCESS"
            ),
            reason="Tamper test",
        )
    )

    approval_id = created[
        "approval"
    ]["approval_id"]

    with remediation_approval_service._connect() as connection:
        connection.execute(
            """
            UPDATE approvals
            SET router_ip='10.0.0.1'
            WHERE approval_id=?
            """,
            (
                approval_id,
            ),
        )

        connection.commit()

    validation = (
        remediation_approval_service
        .validate_execution_intent(
            approval_id
        )
    )

    assert validation["valid"] is False

    assert (
        validation["reason"]
        == "Execution intent fingerprint mismatch"
    )


def test_expired_intent_cannot_be_approved(
    tmp_path,
    monkeypatch,
) -> None:
    _use_database(
        tmp_path,
        monkeypatch,
    )

    created = (
        remediation_approval_service
        .create_approval_request(
            router_ip="192.168.88.1",
            action_type=(
                "CHECK_CPU_PROCESS"
            ),
            reason="Expiry test",
        )
    )

    approval_id = created[
        "approval"
    ]["approval_id"]

    expired_at = (
        datetime.now(
            timezone.utc
        )
        - timedelta(minutes=1)
    ).isoformat()

    approval = (
        remediation_approval_service
        .get_approval_by_id(
            approval_id
        )
    )

    expired_intent = ExecutionIntent(
        approval_id=approval_id,
        router_ip=approval["router_ip"],
        action_type=approval["action_type"],
        execution_class=(
            approval["execution_class"]
        ),
        read_only=approval["read_only"],
        verification_required=(
            approval[
                "verification_required"
            ]
        ),
        rollback_required=(
            approval[
                "rollback_required"
            ]
        ),
        expires_at=expired_at,
        intent_version=(
            approval["intent_version"]
        ),
    )

    with remediation_approval_service._connect() as connection:
        connection.execute(
            """
            UPDATE approvals
            SET expires_at=?,
                intent_fingerprint=?
            WHERE approval_id=?
            """,
            (
                expired_at,
                expired_intent.fingerprint,
                approval_id,
            ),
        )

        connection.commit()

    result = (
        remediation_approval_service
        .approve_request(
            approval_id
        )
    )

    assert result["success"] is False

    assert (
        result["message"]
        == "Execution intent has expired"
    )
