from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import IPv4Address
import os
from typing import Any
import uuid

from app.services.remediation_approval_service import (
    claim_approval_for_execution,
    finalize_approval_execution,
    get_approval_by_id,
    validate_execution_intent,
)
from app.services.controlled_execution_receipt_store import (
    receipt_store,
)


SERVICE_NAME = (
    "SS4TS Controlled Execution Safety Gate"
)

SERVICE_VERSION = "1.0.0-simulation-only"

ALLOWED_ACTIONS = frozenset({
    "CHECK_CPU_PROCESS",
    "CHECK_FIREWALL_LOAD",
    "ANALYZE_TRAFFIC_LOAD",
})


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def controlled_execution_enabled() -> bool:
    return (
        os.getenv(
            "SS4TS_CONTROLLED_EXECUTION_ENABLED",
            "false",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def _response(
    *,
    status: str,
    approval_id: str,
    reason: str,
    approval: dict[str, Any] | None = None,
    execution_id: str | None = None,
) -> dict[str, Any]:
    return {
        "engine": {
            "name": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },
        "execution": {
            "execution_id": execution_id,
            "approval_id": approval_id,
            "status": status,
            "reason": reason,
            "approval": approval,
            "mode": "SAFE_SIMULATION",
            "execution_enabled":
                controlled_execution_enabled(),
            "network_io_performed": False,
            "device_command_executed": False,
            "created_at": _utc_now(),
        },
    }


def execute_controlled_remediation(
    *,
    approval_id: str,
    requested_router_ip: str | None = None,
    requested_action_type: str | None = None,
) -> dict[str, Any]:
    """
    Execute a persistently approved action through a simulation-only gate.

    Security guarantees:
    - feature flag defaults to OFF;
    - router and action remain bound to the approval record;
    - only an allowlisted read-only action is accepted;
    - each approval can be claimed exactly once;
    - no RouterOS connection or device command is performed.
    """
    approval = get_approval_by_id(
        approval_id
    )

    if approval is None:
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason="Approval request not found",
        )

    if approval.get("status") != "APPROVED":
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason="Approval is not executable",
            approval=approval,
        )

    intent_validation = (
        validate_execution_intent(
            approval_id
        )
    )

    if not intent_validation["valid"]:
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason=str(
                intent_validation["reason"]
            ),
            approval=approval,
        )

    approved_router_ip = str(
        approval.get(
            "router_ip",
            "",
        )
    ).strip()

    approved_action_type = str(
        approval.get(
            "action_type",
            "",
        )
    ).strip()

    try:
        approved_router_ip = str(
            IPv4Address(
                approved_router_ip
            )
        )
    except ValueError:
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason=(
                "Approval contains an invalid "
                "IPv4 address"
            ),
            approval=approval,
        )

    if (
        requested_router_ip is not None
        and str(
            requested_router_ip
        ).strip()
        != approved_router_ip
    ):
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason=(
                "Requested router does not match "
                "the approved router"
            ),
            approval=approval,
        )

    if (
        requested_action_type is not None
        and str(
            requested_action_type
        ).strip()
        != approved_action_type
    ):
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason=(
                "Requested action does not match "
                "the approved action"
            ),
            approval=approval,
        )

    if approved_action_type not in ALLOWED_ACTIONS:
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason=(
                "Action is not included in the "
                "controlled execution allowlist"
            ),
            approval=approval,
        )

    if not controlled_execution_enabled():
        return _response(
            status="DISABLED",
            approval_id=approval_id,
            reason=(
                "Controlled execution is disabled "
                "by the production safety switch"
            ),
            approval=approval,
        )

    claimed = claim_approval_for_execution(
        approval_id
    )

    if not claimed.get("claimed"):
        return _response(
            status="REJECTED",
            approval_id=approval_id,
            reason=str(
                claimed.get(
                    "reason",
                    "Approval could not be claimed",
                )
            ),
            approval=claimed.get(
                "approval"
            ),
        )

    execution_id = str(
        uuid.uuid4()
    )

    receipt_store.create_started(
        execution_id=execution_id,
        approval_id=approval_id,
        intent_fingerprint=(
            intent_validation[
                "intent"
            ][
                "intent_fingerprint"
            ]
        ),
        intent_version=(
            intent_validation[
                "intent"
            ][
                "intent_version"
            ]
        ),
        router_ip=approved_router_ip,
        action_type=approved_action_type,
        approval_status_before="APPROVED",
    )

    try:
        completed = (
            finalize_approval_execution(
                approval_id,
                succeeded=True,
            )
        )

        if completed is None:
            raise RuntimeError(
                "Approval finalization failed"
            )

        receipt = receipt_store.finalize(
            execution_id,
            status="SIMULATED_SUCCESS",
            approval_status_after="EXECUTED",
            verification_status=(
                "SIMULATED_VERIFIED"
            ),
        )

        result = _response(
            status="SIMULATED_SUCCESS",
            approval_id=approval_id,
            execution_id=execution_id,
            reason=(
                "Controlled remediation simulation "
                "completed"
            ),
            approval=completed,
        )

        result["execution"].update({
            "router_ip":
                approved_router_ip,
            "action_type":
                approved_action_type,
            "intent_fingerprint":
                intent_validation[
                    "intent"
                ][
                    "intent_fingerprint"
                ],
            "intent_version":
                intent_validation[
                    "intent"
                ][
                    "intent_version"
                ],
            "verification_status":
                "SIMULATED_VERIFIED",
            "approval_consumed":
                True,
            "receipt":
                receipt.to_dict(),
        })

        return result

    except Exception as exc:
        failed_approval = (
            finalize_approval_execution(
                approval_id,
                succeeded=False,
            )
        )

        try:
            receipt_store.finalize(
                execution_id,
                status="FAILED",
                approval_status_after=(
                    "EXECUTION_FAILED"
                ),
                verification_status=(
                    "FAILED"
                ),
                failure_reason=str(exc),
            )
        except Exception:
            pass

        return _response(
            status="FAILED",
            approval_id=approval_id,
            execution_id=execution_id,
            reason=str(exc),
            approval=get_approval_by_id(
                approval_id
            ),
        )
