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


def test_canary_read_only_receipt_records_network_io(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    started = store.create_started(
        execution_id="execution-canary-1",
        approval_id="approval-canary-1",
        intent_fingerprint="f" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_SYSTEM_RESOURCE",
        approval_status_before="APPROVED",
        mode="CANARY_READ_ONLY",
    )

    assert (
        started.mode
        == "CANARY_READ_ONLY"
    )

    assert (
        started.network_io_performed
        is False
    )

    completed = store.finalize(
        "execution-canary-1",
        status="READ_ONLY_SUCCESS",
        approval_status_after="EXECUTED",
        verification_status=(
            "READ_ONLY_VERIFIED"
        ),
        network_io_performed=True,
    )

    assert (
        completed.network_io_performed
        is True
    )

    assert (
        completed.device_command_executed
        is False
    )

    payload = completed.to_dict()

    assert (
        payload["safety"][
            "network_io_performed"
        ]
        is True
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )

    assert (
        payload["safety"]["read_only"]
        is True
    )

    loaded = store.get(
        "execution-canary-1"
    )

    assert loaded == completed


def test_safe_simulation_cannot_claim_network_io(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    store.create_started(
        execution_id="execution-simulation-io",
        approval_id="approval-simulation-io",
        intent_fingerprint="g" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    with pytest.raises(
        ValueError,
        match="CANARY_READ_ONLY",
    ):
        store.finalize(
            "execution-simulation-io",
            status="SIMULATED_SUCCESS",
            approval_status_after="EXECUTED",
            verification_status=(
                "SIMULATED_VERIFIED"
            ),
            network_io_performed=True,
        )


def test_receipt_cannot_claim_device_command_execution(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    store.create_started(
        execution_id="execution-device-command",
        approval_id="approval-device-command",
        intent_fingerprint="h" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_SYSTEM_RESOURCE",
        approval_status_before="APPROVED",
        mode="CANARY_READ_ONLY",
    )

    with pytest.raises(
        ValueError,
        match="device command",
    ):
        store.finalize(
            "execution-device-command",
            status="READ_ONLY_SUCCESS",
            approval_status_after="EXECUTED",
            verification_status=(
                "READ_ONLY_VERIFIED"
            ),
            network_io_performed=True,
            device_command_executed=True,
        )


def test_canary_receipt_durably_marks_network_attempt(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    started = store.create_started(
        execution_id="execution-attempt",
        approval_id="approval-attempt",
        intent_fingerprint="i" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_SYSTEM_RESOURCE",
        approval_status_before="APPROVED",
        mode="CANARY_READ_ONLY",
    )

    assert (
        started.network_io_attempted
        is False
    )

    marked = (
        store.mark_network_io_attempted(
            "execution-attempt"
        )
    )

    assert (
        marked.network_io_attempted
        is True
    )

    assert (
        marked.network_io_performed
        is False
    )

    loaded = store.get(
        "execution-attempt"
    )

    assert (
        loaded.network_io_attempted
        is True
    )

    assert (
        loaded.network_io_performed
        is False
    )

    assert (
        loaded.status
        == "STARTED"
    )


def test_simulation_cannot_mark_network_attempt(
    tmp_path,
) -> None:
    store = _store(
        tmp_path
    )

    store.create_started(
        execution_id="execution-no-attempt",
        approval_id="approval-no-attempt",
        intent_fingerprint="j" * 64,
        intent_version="1.0",
        router_ip="192.168.88.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    with pytest.raises(
        ValueError,
        match="CANARY_READ_ONLY",
    ):
        store.mark_network_io_attempted(
            "execution-no-attempt"
        )


def _create_legacy_receipt_database(
    database,
    *,
    tampered: bool = False,
) -> None:
    import hashlib
    import json

    values = {
        "execution_id":
            "legacy-execution-1",
        "approval_id":
            "legacy-approval-1",
        "intent_fingerprint":
            "k" * 64,
        "intent_version":
            "1.0",
        "router_ip":
            "192.168.88.1",
        "action_type":
            "CHECK_SYSTEM_RESOURCE",
        "mode":
            "CANARY_READ_ONLY",
        "status":
            "STARTED",
        "approval_status_before":
            "APPROVED",
        "approval_status_after":
            "EXECUTING",
        "verification_status":
            None,
        "failure_reason":
            None,
        "started_at":
            "2026-08-09T20:00:00+00:00",
        "completed_at":
            None,
        "network_io_performed":
            False,
        "device_command_executed":
            False,
    }

    canonical = json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )

    checksum = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            CREATE TABLE
            controlled_execution_receipts
            (
                execution_id TEXT PRIMARY KEY,
                approval_id TEXT NOT NULL,
                intent_fingerprint TEXT NOT NULL,
                intent_version TEXT NOT NULL,
                router_ip TEXT NOT NULL,
                action_type TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                approval_status_before TEXT NOT NULL,
                approval_status_after TEXT,
                verification_status TEXT,
                failure_reason TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                network_io_performed INTEGER NOT NULL,
                device_command_executed INTEGER NOT NULL,
                checksum TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT INTO
            controlled_execution_receipts
            (
                execution_id,
                approval_id,
                intent_fingerprint,
                intent_version,
                router_ip,
                action_type,
                mode,
                status,
                approval_status_before,
                approval_status_after,
                verification_status,
                failure_reason,
                started_at,
                completed_at,
                network_io_performed,
                device_command_executed,
                checksum
            )
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
             ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values["execution_id"],
                values["approval_id"],
                values["intent_fingerprint"],
                values["intent_version"],
                (
                    "10.10.10.10"
                    if tampered
                    else values["router_ip"]
                ),
                values["action_type"],
                values["mode"],
                values["status"],
                values[
                    "approval_status_before"
                ],
                values[
                    "approval_status_after"
                ],
                values[
                    "verification_status"
                ],
                values["failure_reason"],
                values["started_at"],
                values["completed_at"],
                int(
                    values[
                        "network_io_performed"
                    ]
                ),
                int(
                    values[
                        "device_command_executed"
                    ]
                ),
                checksum,
            ),
        )

        connection.commit()


def test_valid_legacy_receipt_database_migrates(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "legacy-receipts.db"
    )

    _create_legacy_receipt_database(
        database
    )

    store = (
        ControlledExecutionReceiptStore(
            database
        )
    )

    receipt = store.get(
        "legacy-execution-1"
    )

    assert receipt is not None

    assert (
        receipt.network_io_attempted
        is False
    )

    assert (
        receipt.network_io_performed
        is False
    )

    assert receipt.verify(
        receipt.checksum
    )

    with sqlite3.connect(
        database
    ) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    controlled_execution_receipts
                )
                """
            ).fetchall()
        }

    assert (
        "network_io_attempted"
        in columns
    )


def test_tampered_legacy_receipt_migration_fails_closed(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "legacy-tampered.db"
    )

    _create_legacy_receipt_database(
        database,
        tampered=True,
    )

    with pytest.raises(
        ValueError,
        match=(
            "Legacy execution receipt "
            "checksum mismatch"
        ),
    ):
        ControlledExecutionReceiptStore(
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
                    controlled_execution_receipts
                )
                """
            ).fetchall()
        }

    assert (
        "network_io_attempted"
        not in columns
    )
