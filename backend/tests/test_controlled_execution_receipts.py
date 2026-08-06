from __future__ import annotations

import sqlite3

import pytest

from app.services import (
    controlled_execution_gate,
    remediation_approval_service,
)
from app.services.controlled_execution_receipt_store import (
    ControlledExecutionReceiptStore,
)


def _store(
    tmp_path,
) -> ControlledExecutionReceiptStore:
    return ControlledExecutionReceiptStore(
        tmp_path
        / "receipts.db"
    )


def _use_services(
    tmp_path,
    monkeypatch,
):
    approval_database = (
        tmp_path
        / "approvals.db"
    )

    monkeypatch.setattr(
        remediation_approval_service,
        "DB_PATH",
        approval_database,
    )

    remediation_approval_service._init_db()

    store = _store(
        tmp_path
    )

    monkeypatch.setattr(
        controlled_execution_gate,
        "receipt_store",
        store,
    )

    return store


def _approved() -> dict:
    created = (
        remediation_approval_service
        .create_approval_request(
            router_ip="192.168.88.1",
            action_type=(
                "CHECK_CPU_PROCESS"
            ),
            reason="Receipt test",
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

    return approved["approval"]


def test_receipt_store_lifecycle(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    started = store.create_started(
        execution_id="execution-1",
        approval_id="approval-1",
        intent_fingerprint="a" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    assert started.status == "STARTED"
    assert started.completed_at is None

    completed = store.finalize(
        "execution-1",
        status="SIMULATED_SUCCESS",
        approval_status_after="EXECUTED",
        verification_status=(
            "SIMULATED_VERIFIED"
        ),
    )

    assert (
        completed.status
        == "SIMULATED_SUCCESS"
    )

    assert completed.completed_at is not None
    assert len(completed.checksum) == 64

    loaded = store.get(
        "execution-1"
    )

    assert loaded == completed


def test_receipt_cannot_be_finalized_twice(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    store.create_started(
        execution_id="execution-1",
        approval_id="approval-1",
        intent_fingerprint="a" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    store.finalize(
        "execution-1",
        status="SIMULATED_SUCCESS",
        approval_status_after="EXECUTED",
        verification_status=(
            "SIMULATED_VERIFIED"
        ),
    )

    with pytest.raises(
        ValueError,
        match="already finalized",
    ):
        store.finalize(
            "execution-1",
            status="FAILED",
            approval_status_after=(
                "EXECUTION_FAILED"
            ),
            verification_status="FAILED",
        )


def test_receipt_tampering_detected(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    store.create_started(
        execution_id="execution-1",
        approval_id="approval-1",
        intent_fingerprint="a" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            """
            UPDATE controlled_execution_receipts
            SET router_ip='10.0.0.1'
            WHERE execution_id='execution-1'
            """
        )

        connection.commit()

    with pytest.raises(
        ValueError,
        match="checksum mismatch",
    ):
        store.get(
            "execution-1"
        )


def test_controlled_gate_returns_receipt(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_services(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = _approved()

    result = (
        controlled_execution_gate
        .execute_controlled_remediation(
            approval_id=(
                approval["approval_id"]
            ),
        )
    )

    execution = result["execution"]

    assert (
        execution["status"]
        == "SIMULATED_SUCCESS"
    )

    receipt = execution["receipt"]

    assert (
        receipt["execution_id"]
        == execution["execution_id"]
    )

    assert (
        receipt["intent_fingerprint"]
        == approval[
            "intent_fingerprint"
        ]
    )

    assert (
        receipt["network_io_performed"]
        is False
    )

    assert (
        receipt["device_command_executed"]
        is False
    )

    loaded = store.get(
        execution["execution_id"]
    )

    assert (
        loaded.status
        == "SIMULATED_SUCCESS"
    )


def test_receipts_can_be_retrieved_by_approval(
    tmp_path,
    monkeypatch,
) -> None:
    store = _use_services(
        tmp_path,
        monkeypatch,
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = _approved()

    result = (
        controlled_execution_gate
        .execute_controlled_remediation(
            approval_id=(
                approval["approval_id"]
            ),
        )
    )

    receipts = store.by_approval(
        approval["approval_id"]
    )

    assert len(receipts) == 1

    assert (
        receipts[0].execution_id
        == result["execution"][
            "execution_id"
        ]
    )
