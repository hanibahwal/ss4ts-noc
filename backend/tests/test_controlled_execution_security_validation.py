from __future__ import annotations

import asyncio
import sqlite3
import threading
import uuid

from concurrent.futures import (
    ThreadPoolExecutor,
)
from pathlib import Path

import pytest

from app.api.v1 import (
    controlled_execution_recovery_runtime as runtime_api,
)
from app.services.controlled_execution_gate import (
    execute_controlled_remediation,
)
from app.services.controlled_execution_receipt_store import (
    ControlledExecutionReceiptStore,
)
from app.services.controlled_execution_recovery import (
    ControlledExecutionRecovery,
)
from app.services.controlled_execution_recovery_runtime import (
    CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
    ControlledExecutionRecoveryRuntime,
)
from app.services import controlled_execution_gate as gate
from app.services import controlled_execution_recovery as recovery_module


def run(
    coroutine,
):
    return asyncio.run(
        coroutine
    )


def make_approval(
    *,
    approval_id: str = "approval-security-1",
    status: str = "APPROVED",
    router_ip: str = "192.168.10.1",
    action_type: str = "CHECK_CPU_PROCESS",
) -> dict:
    return {
        "approval_id": approval_id,
        "status": status,
        "router_ip": router_ip,
        "action_type": action_type,
    }


def make_valid_intent(
    *,
    approval_id: str = "approval-security-1",
) -> dict:
    return {
        "valid": True,
        "reason": "VALID",
        "intent": {
            "approval_id": approval_id,
            "intent_fingerprint":
                "a" * 64,
            "intent_version":
                "1.0",
        },
    }


def patch_gate_approval(
    monkeypatch,
    *,
    approval: dict,
) -> None:
    monkeypatch.setattr(
        gate,
        "get_approval_by_id",
        lambda approval_id: dict(
            approval
        ),
    )

    monkeypatch.setattr(
        gate,
        "validate_execution_intent",
        lambda approval_id: (
            make_valid_intent(
                approval_id=approval_id
            )
        ),
    )


def test_feature_switch_defaults_fail_closed(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        raising=False,
    )

    approval = make_approval()

    patch_gate_approval(
        monkeypatch,
        approval=approval,
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ]
    )

    assert (
        result["execution"]["status"]
        == "DISABLED"
    )

    assert (
        result["execution"][
            "network_io_performed"
        ]
        is False
    )

    assert (
        result["execution"][
            "device_command_executed"
        ]
        is False
    )


def test_missing_approval_is_rejected(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        gate,
        "get_approval_by_id",
        lambda approval_id: None,
    )

    result = execute_controlled_remediation(
        approval_id="missing-approval"
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        result["execution"]["reason"]
        == "Approval request not found"
    )


def test_non_approved_state_is_rejected(
    monkeypatch,
) -> None:
    approval = make_approval(
        status="EXECUTING"
    )

    monkeypatch.setattr(
        gate,
        "get_approval_by_id",
        lambda approval_id: approval,
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ]
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        result["execution"]["reason"]
        == "Approval is not executable"
    )


def test_tampered_intent_is_rejected_before_claim(
    monkeypatch,
) -> None:
    approval = make_approval()

    monkeypatch.setattr(
        gate,
        "get_approval_by_id",
        lambda approval_id: approval,
    )

    monkeypatch.setattr(
        gate,
        "validate_execution_intent",
        lambda approval_id: {
            "valid": False,
            "reason":
                "Execution intent fingerprint mismatch",
            "intent": None,
        },
    )

    claimed = {
        "called": False
    }

    def claim(
        approval_id: str,
    ) -> dict:
        claimed["called"] = True

        return {
            "claimed": True,
        }

    monkeypatch.setattr(
        gate,
        "claim_approval_for_execution",
        claim,
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ]
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert claimed["called"] is False


def test_requested_router_tampering_is_rejected(
    monkeypatch,
) -> None:
    approval = make_approval()

    patch_gate_approval(
        monkeypatch,
        approval=approval,
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ],
        requested_router_ip=(
            "192.168.10.254"
        ),
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        "does not match"
        in result["execution"]["reason"]
    )


def test_requested_action_tampering_is_rejected(
    monkeypatch,
) -> None:
    approval = make_approval()

    patch_gate_approval(
        monkeypatch,
        approval=approval,
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ],
        requested_action_type=(
            "REBOOT_ROUTER"
        ),
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        "does not match"
        in result["execution"]["reason"]
    )


def test_non_allowlisted_action_is_rejected(
    monkeypatch,
) -> None:
    approval = make_approval(
        action_type="REBOOT_ROUTER"
    )

    patch_gate_approval(
        monkeypatch,
        approval=approval,
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ]
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        "allowlist"
        in result["execution"]["reason"]
    )


def test_duplicate_claim_is_rejected(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = make_approval()

    patch_gate_approval(
        monkeypatch,
        approval=approval,
    )

    monkeypatch.setattr(
        gate,
        "claim_approval_for_execution",
        lambda approval_id: {
            "claimed": False,
            "reason":
                "Approval is already claimed",
            "approval": {
                **approval,
                "status": "EXECUTING",
            },
        },
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ]
    )

    assert (
        result["execution"]["status"]
        == "REJECTED"
    )

    assert (
        "already claimed"
        in result["execution"]["reason"]
    )


def test_receipt_creation_failure_does_not_execute_device(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = make_approval()

    patch_gate_approval(
        monkeypatch,
        approval=approval,
    )

    monkeypatch.setattr(
        gate,
        "claim_approval_for_execution",
        lambda approval_id: {
            "claimed": True,
            "approval": {
                **approval,
                "status": "EXECUTING",
            },
        },
    )

    def fail_receipt(
        **kwargs,
    ):
        raise sqlite3.OperationalError(
            "receipt storage unavailable"
        )

    monkeypatch.setattr(
        gate.receipt_store,
        "create_started",
        fail_receipt,
    )

    with pytest.raises(
        sqlite3.OperationalError,
        match="receipt storage unavailable",
    ):
        execute_controlled_remediation(
            approval_id=approval[
                "approval_id"
            ]
        )


def test_finalization_failure_returns_failed_closed(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SS4TS_CONTROLLED_EXECUTION_ENABLED",
        "true",
    )

    approval = make_approval()

    patch_gate_approval(
        monkeypatch,
        approval=approval,
    )

    monkeypatch.setattr(
        gate,
        "claim_approval_for_execution",
        lambda approval_id: {
            "claimed": True,
            "approval": {
                **approval,
                "status": "EXECUTING",
            },
        },
    )

    class FakeReceipt:
        def to_dict(
            self,
        ) -> dict:
            return {
                "status": "STARTED",
            }

    monkeypatch.setattr(
        gate.receipt_store,
        "create_started",
        lambda **kwargs: FakeReceipt(),
    )

    calls: list[bool] = []

    def finalize(
        approval_id: str,
        *,
        succeeded: bool,
    ):
        calls.append(
            succeeded
        )

        if succeeded:
            raise RuntimeError(
                "forced finalization failure"
            )

        return {
            **approval,
            "status": "EXECUTION_FAILED",
        }

    monkeypatch.setattr(
        gate,
        "finalize_approval_execution",
        finalize,
    )

    monkeypatch.setattr(
        gate.receipt_store,
        "finalize",
        lambda *args, **kwargs: FakeReceipt(),
    )

    result = execute_controlled_remediation(
        approval_id=approval[
            "approval_id"
        ]
    )

    assert (
        result["execution"]["status"]
        == "FAILED"
    )

    assert calls == [
        True,
        False,
    ]

    assert (
        result["execution"][
            "device_command_executed"
        ]
        is False
    )


def test_receipt_checksum_tampering_is_detected(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "controlled-receipts.db"
    )

    store = (
        ControlledExecutionReceiptStore(
            database
        )
    )

    execution_id = str(
        uuid.uuid4()
    )

    store.create_started(
        execution_id=execution_id,
        approval_id="approval-tamper",
        intent_fingerprint="b" * 64,
        intent_version="1.0",
        router_ip="192.168.10.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE controlled_execution_receipts
            SET router_ip=?
            WHERE execution_id=?
            """,
            (
                "192.168.10.254",
                execution_id,
            ),
        )

        connection.commit()

    with pytest.raises(
        ValueError,
        match="checksum mismatch",
    ):
        store.get(
            execution_id
        )


def test_receipt_cannot_be_finalized_twice(
    tmp_path: Path,
) -> None:
    store = (
        ControlledExecutionReceiptStore(
            tmp_path
            / "controlled-receipts.db"
        )
    )

    execution_id = str(
        uuid.uuid4()
    )

    store.create_started(
        execution_id=execution_id,
        approval_id="approval-finalize",
        intent_fingerprint="c" * 64,
        intent_version="1.0",
        router_ip="192.168.10.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    store.finalize(
        execution_id,
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
            execution_id,
            status="FAILED",
            approval_status_after=(
                "EXECUTION_FAILED"
            ),
            verification_status="FAILED",
        )


def test_duplicate_execution_id_is_rejected(
    tmp_path: Path,
) -> None:
    store = (
        ControlledExecutionReceiptStore(
            tmp_path
            / "controlled-receipts.db"
        )
    )

    execution_id = str(
        uuid.uuid4()
    )

    arguments = {
        "execution_id":
            execution_id,
        "approval_id":
            "approval-duplicate",
        "intent_fingerprint":
            "d" * 64,
        "intent_version":
            "1.0",
        "router_ip":
            "192.168.10.1",
        "action_type":
            "CHECK_CPU_PROCESS",
        "approval_status_before":
            "APPROVED",
    }

    store.create_started(
        **arguments
    )

    with pytest.raises(
        sqlite3.IntegrityError
    ):
        store.create_started(
            **arguments
        )


def test_concurrent_duplicate_receipt_creation_has_one_winner(
    tmp_path: Path,
) -> None:
    store = (
        ControlledExecutionReceiptStore(
            tmp_path
            / "controlled-receipts.db"
        )
    )

    execution_id = str(
        uuid.uuid4()
    )

    barrier = threading.Barrier(
        2
    )

    def create(
    ) -> str:
        barrier.wait()

        try:
            store.create_started(
                execution_id=execution_id,
                approval_id=(
                    "approval-concurrent"
                ),
                intent_fingerprint=(
                    "e" * 64
                ),
                intent_version="1.0",
                router_ip="192.168.10.1",
                action_type=(
                    "CHECK_CPU_PROCESS"
                ),
                approval_status_before=(
                    "APPROVED"
                ),
            )

            return "CREATED"

        except sqlite3.IntegrityError:
            return "REJECTED"

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        results = list(
            executor.map(
                lambda _: create(),
                range(2),
            )
        )

    assert sorted(
        results
    ) == [
        "CREATED",
        "REJECTED",
    ]


def test_corrupted_receipt_stops_reconciliation(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "controlled-receipts.db"
    )

    store = (
        ControlledExecutionReceiptStore(
            database
        )
    )

    execution_id = str(
        uuid.uuid4()
    )

    store.create_started(
        execution_id=execution_id,
        approval_id="approval-corrupt",
        intent_fingerprint="f" * 64,
        intent_version="1.0",
        router_ip="192.168.10.1",
        action_type="CHECK_CPU_PROCESS",
        approval_status_before="APPROVED",
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE controlled_execution_receipts
            SET started_at=?,
                checksum=?
            WHERE execution_id=?
            """,
            (
                "2000-01-01T00:00:00+00:00",
                "invalid-checksum",
                execution_id,
            ),
        )

        connection.commit()

    recovery = (
        ControlledExecutionRecovery(
            store=store
        )
    )

    with pytest.raises(
        ValueError,
        match="checksum mismatch",
    ):
        recovery.reconcile(
            stale_after_seconds=1,
            limit=100,
        )


@pytest.mark.asyncio
async def test_runtime_failure_is_recorded_and_reraised(
) -> None:
    class FailedRecovery:
        def reconcile(
            self,
            *,
            stale_after_seconds: int,
            limit: int,
        ) -> dict:
            raise RuntimeError(
                "injected recovery failure"
            )

    runtime = (
        ControlledExecutionRecoveryRuntime(
            recovery=FailedRecovery(),
            interval_seconds=1,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="injected recovery failure",
    ):
        await runtime.run_cycle()

    assert (
        runtime.state.failed_cycle_count
        == 1
    )

    assert runtime.state.cycle_count == 1

    assert (
        runtime.state.last_error
        == "injected recovery failure"
    )


@pytest.mark.asyncio
async def test_runtime_background_loop_survives_failed_cycle(
) -> None:
    class FlakyRecovery:
        def __init__(
            self,
        ) -> None:
            self.calls = 0

        def reconcile(
            self,
            *,
            stale_after_seconds: int,
            limit: int,
        ) -> dict:
            self.calls += 1

            if self.calls == 1:
                raise RuntimeError(
                    "first cycle failed"
                )

            return {
                "recovery": {
                    "recovered_count": 0,
                }
            }

    recovery = FlakyRecovery()

    runtime = (
        ControlledExecutionRecoveryRuntime(
            recovery=recovery,
            interval_seconds=1,
        )
    )

    assert await runtime.start() is True

    await asyncio.sleep(
        1.15
    )

    assert recovery.calls >= 2

    assert (
        runtime.state.failed_cycle_count
        >= 1
    )

    assert (
        runtime.state.successful_cycle_count
        >= 1
    )

    assert runtime.is_running is True

    assert await runtime.stop() is True


def test_disabled_environment_rejects_runtime_start(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    with pytest.raises(
        Exception
    ) as exc_info:
        run(
            runtime_api
            .start_controlled_recovery_runtime()
        )

    exception = exc_info.value

    assert getattr(
        exception,
        "status_code",
        None,
    ) == 409

    assert (
        exception.detail["type"]
        == "runtime_environment_disabled"
    )


def test_recovery_failure_does_not_claim_or_execute_device(
    monkeypatch,
) -> None:
    class FailedStore:
        def started_before(
            self,
            cutoff_at: str,
            *,
            limit: int,
        ):
            raise RuntimeError(
                "receipt database unavailable"
            )

    recovery = (
        ControlledExecutionRecovery(
            store=FailedStore()
        )
    )

    monkeypatch.setattr(
        recovery_module,
        "recover_executing_approval_as_failed",
        lambda approval_id: pytest.fail(
            "Approval must not be mutated"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="receipt database unavailable",
    ):
        recovery.reconcile()

