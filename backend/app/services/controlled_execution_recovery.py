from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

from app.services.controlled_execution_receipt_store import (
    ControlledExecutionReceiptStore,
    receipt_store,
)
from app.services.remediation_approval_service import (
    get_approval_by_id,
    get_executing_approvals,
    recover_executing_approval_as_failed,
)


SERVICE_NAME = (
    "SS4TS Controlled Execution "
    "Recovery Reconciliation"
)

SERVICE_VERSION = "1.0.0-fail-closed"

DEFAULT_STALE_AFTER_SECONDS = 300
DEFAULT_RECOVERY_LIMIT = 100


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _cutoff(
    stale_after_seconds: int,
) -> str:
    if stale_after_seconds < 1:
        raise ValueError(
            "stale_after_seconds must be positive"
        )

    return (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            seconds=stale_after_seconds
        )
    ).isoformat()


class ControlledExecutionRecovery:
    def __init__(
        self,
        *,
        store: (
            ControlledExecutionReceiptStore
        ) = receipt_store,
    ) -> None:
        self.store = store

    def reconcile(
        self,
        *,
        stale_after_seconds: int = (
            DEFAULT_STALE_AFTER_SECONDS
        ),
        limit: int = DEFAULT_RECOVERY_LIMIT,
    ) -> dict[str, Any]:
        safe_limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

        cutoff_at = _cutoff(
            int(stale_after_seconds)
        )

        events: list[dict[str, Any]] = []
        processed_approvals: set[str] = set()

        stale_receipts = (
            self.store.started_before(
                cutoff_at,
                limit=safe_limit,
            )
        )

        for receipt in stale_receipts:
            approval = get_approval_by_id(
                receipt.approval_id
            )

            if approval is None:
                finalized = self.store.finalize(
                    receipt.execution_id,
                    status="RECOVERED_FAILED",
                    approval_status_after=(
                        "MISSING"
                    ),
                    verification_status=(
                        "RECOVERY_FAILED"
                    ),
                    failure_reason=(
                        "Approval record missing "
                        "during recovery"
                    ),
                )

                events.append({
                    "execution_id":
                        receipt.execution_id,
                    "approval_id":
                        receipt.approval_id,
                    "decision":
                        "RECEIPT_FAILED",
                    "reason":
                        "APPROVAL_MISSING",
                    "receipt":
                        finalized.to_dict(),
                })

                processed_approvals.add(
                    receipt.approval_id
                )

                continue

            approval_status = str(
                approval.get(
                    "status",
                    "",
                )
            )

            if approval_status == "EXECUTED":
                finalized = self.store.finalize(
                    receipt.execution_id,
                    status="RECOVERED_SUCCESS",
                    approval_status_after=(
                        "EXECUTED"
                    ),
                    verification_status=(
                        "RECOVERED_VERIFIED"
                    ),
                    failure_reason=None,
                )

                events.append({
                    "execution_id":
                        receipt.execution_id,
                    "approval_id":
                        receipt.approval_id,
                    "decision":
                        "RECEIPT_COMPLETED",
                    "reason":
                        "APPROVAL_ALREADY_EXECUTED",
                    "receipt":
                        finalized.to_dict(),
                })

            elif approval_status == "EXECUTING":
                recovered_approval = (
                    recover_executing_approval_as_failed(
                        receipt.approval_id
                    )
                )

                finalized = self.store.finalize(
                    receipt.execution_id,
                    status="RECOVERED_FAILED",
                    approval_status_after=(
                        "EXECUTION_FAILED"
                    ),
                    verification_status=(
                        "RECOVERY_FAILED"
                    ),
                    failure_reason=(
                        "Stale controlled execution "
                        "recovered after interruption"
                    ),
                )

                events.append({
                    "execution_id":
                        receipt.execution_id,
                    "approval_id":
                        receipt.approval_id,
                    "decision":
                        "EXECUTION_FAILED_CLOSED",
                    "reason":
                        "STALE_EXECUTING",
                    "approval":
                        recovered_approval,
                    "receipt":
                        finalized.to_dict(),
                })

            else:
                finalized = self.store.finalize(
                    receipt.execution_id,
                    status="RECOVERED_FAILED",
                    approval_status_after=(
                        approval_status
                        or "UNKNOWN"
                    ),
                    verification_status=(
                        "RECOVERY_FAILED"
                    ),
                    failure_reason=(
                        "Receipt and approval states "
                        "were inconsistent"
                    ),
                )

                events.append({
                    "execution_id":
                        receipt.execution_id,
                    "approval_id":
                        receipt.approval_id,
                    "decision":
                        "RECEIPT_FAILED",
                    "reason":
                        "STATE_MISMATCH",
                    "receipt":
                        finalized.to_dict(),
                })

            processed_approvals.add(
                receipt.approval_id
            )

        remaining = max(
            0,
            safe_limit - len(events),
        )

        if remaining:
            for approval in (
                get_executing_approvals()
            ):
                if len(events) >= safe_limit:
                    break

                approval_id = str(
                    approval["approval_id"]
                )

                if (
                    approval_id
                    in processed_approvals
                ):
                    continue

                if self.store.has_receipt_for_approval(
                    approval_id
                ):
                    continue

                recovered = (
                    recover_executing_approval_as_failed(
                        approval_id
                    )
                )

                if recovered is None:
                    continue

                events.append({
                    "execution_id": None,
                    "approval_id":
                        approval_id,
                    "decision":
                        "ORPHAN_APPROVAL_FAILED",
                    "reason":
                        "NO_EXECUTION_RECEIPT",
                    "approval":
                        recovered,
                })

        return {
            "engine": {
                "name": SERVICE_NAME,
                "version": SERVICE_VERSION,
            },
            "recovery": {
                "status": "COMPLETED",
                "cutoff_at": cutoff_at,
                "stale_after_seconds":
                    stale_after_seconds,
                "limit": safe_limit,
                "recovered_count":
                    len(events),
                "events": events,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
                "completed_at": _utc_now(),
            },
        }


recovery_service = (
    ControlledExecutionRecovery()
)
