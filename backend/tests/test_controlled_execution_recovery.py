from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import sqlite3

from app.services import (
    remediation_approval_service,
)
from app.services.controlled_execution_receipt_store import (
    ControlledExecutionReceiptStore,
)
from app.services.controlled_execution_recovery import (
    ControlledExecutionRecovery,
)


def _past() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        - timedelta(minutes=30)
    ).isoformat()


def _setup(
    tmp_path,
    monkeypatch,
):
    approval_db = (
        tmp_path
        / "approvals.db"
    )

    monkeypatch.setattr(
        remediation_approval_service,
        "DB_PATH",
        approval_db,
    )

    remediation_approval_service._init_db()

    store = ControlledExecutionReceiptStore(
        tmp_path
        / "receipts.db"
    )

    recovery = ControlledExecutionRecovery(
        store=store
    )

    return store, recovery


def _approved_and_claimed() -> dict:
    created = (
        remediation_approval_service
        .create_approval_request(
            router_ip="192.168.88.1",
            action_type=(
                "CHECK_CPU_PROCESS"
            ),
            reason="Recovery test",
        )
    )

    approval_id = created[
        "approval"
    ]["approval_id"]

    approved = (
        remediation_approval_service
        .approve_request(
            approval_id
        )
    )

    assert approved["success"] is True

    claimed = (
        remediation_approval_service
        .claim_approval_for_execution(
            approval_id
        )
    )

    assert claimed["claimed"] is True

    return claimed["approval"]


def _started_receipt(
    store,
    approval,
    *,
    execution_id: str,
):
    receipt = store.create_started(
        execution_id=execution_id,
        approval_id=(
            approval["approval_id"]
        ),
        intent_fingerprint=(
            approval["intent_fingerprint"]
        ),
        intent_version=(
            approval["intent_version"]
        ),
        router_ip=approval["router_ip"],
        action_type=approval["action_type"],
        approval_status_before="APPROVED",
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            """
            UPDATE controlled_execution_receipts
            SET started_at=?
            WHERE execution_id=?
            """,
            (
                _past(),
                execution_id,
            ),
        )

        connection.commit()

    # Rebuild the checksum after changing started_at.
    with store._connect() as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM controlled_execution_receipts
            WHERE execution_id=?
            """,
            (
                execution_id,
            ),
        ).fetchone()

        rebuilt = store._receipt(row)

        connection.execute(
            """
            UPDATE controlled_execution_receipts
            SET checksum=?
            WHERE execution_id=?
            """,
            (
                rebuilt.checksum,
                execution_id,
            ),
        )

        connection.commit()

    return receipt


def test_recovers_stale_executing_as_failed(
    tmp_path,
    monkeypatch,
) -> None:
    store, recovery = _setup(
        tmp_path,
        monkeypatch,
    )

    approval = _approved_and_claimed()

    _started_receipt(
        store,
        approval,
        execution_id="execution-1",
    )

    result = recovery.reconcile(
        stale_after_seconds=60
    )

    assert (
        result["recovery"][
            "recovered_count"
        ]
        == 1
    )

    recovered_approval = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert (
        recovered_approval["status"]
        == "EXECUTION_FAILED"
    )

    receipt = store.get(
        "execution-1"
    )

    assert (
        receipt.status
        == "RECOVERED_FAILED"
    )


def test_recovers_started_receipt_when_approval_executed(
    tmp_path,
    monkeypatch,
) -> None:
    store, recovery = _setup(
        tmp_path,
        monkeypatch,
    )

    approval = _approved_and_claimed()

    _started_receipt(
        store,
        approval,
        execution_id="execution-2",
    )

    finalized = (
        remediation_approval_service
        .finalize_approval_execution(
            approval["approval_id"],
            succeeded=True,
        )
    )

    assert finalized["status"] == "EXECUTED"

    recovery.reconcile(
        stale_after_seconds=60
    )

    receipt = store.get(
        "execution-2"
    )

    assert (
        receipt.status
        == "RECOVERED_SUCCESS"
    )

    assert (
        receipt.verification_status
        == "RECOVERED_VERIFIED"
    )


def test_recovers_orphan_executing_approval(
    tmp_path,
    monkeypatch,
) -> None:
    _, recovery = _setup(
        tmp_path,
        monkeypatch,
    )

    approval = _approved_and_claimed()

    result = recovery.reconcile(
        stale_after_seconds=60
    )

    recovered = (
        remediation_approval_service
        .get_approval_by_id(
            approval["approval_id"]
        )
    )

    assert (
        recovered["status"]
        == "EXECUTION_FAILED"
    )

    assert (
        result["recovery"][
            "events"
        ][0]["decision"]
        == "ORPHAN_APPROVAL_FAILED"
    )


def test_recovery_is_idempotent(
    tmp_path,
    monkeypatch,
) -> None:
    _, recovery = _setup(
        tmp_path,
        monkeypatch,
    )

    _approved_and_claimed()

    first = recovery.reconcile(
        stale_after_seconds=60
    )

    second = recovery.reconcile(
        stale_after_seconds=60
    )

    assert (
        first["recovery"][
            "recovered_count"
        ]
        == 1
    )

    assert (
        second["recovery"][
            "recovered_count"
        ]
        == 0
    )


def test_recent_started_receipt_is_not_recovered(
    tmp_path,
    monkeypatch,
) -> None:
    store, recovery = _setup(
        tmp_path,
        monkeypatch,
    )

    approval = _approved_and_claimed()

    store.create_started(
        execution_id="execution-recent",
        approval_id=(
            approval["approval_id"]
        ),
        intent_fingerprint=(
            approval["intent_fingerprint"]
        ),
        intent_version=(
            approval["intent_version"]
        ),
        router_ip=approval["router_ip"],
        action_type=approval["action_type"],
        approval_status_before="APPROVED",
    )

    result = recovery.reconcile(
        stale_after_seconds=3600
    )

    assert (
        result["recovery"][
            "recovered_count"
        ]
        == 0
    )

    assert (
        store.get(
            "execution-recent"
        ).status
        == "STARTED"
    )
