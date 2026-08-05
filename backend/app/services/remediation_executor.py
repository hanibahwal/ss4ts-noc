from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from app.database import SessionLocal

from app.models.remediation_execution import (
    RemediationExecution,
)

from app.models.remediation_approval import (
    RemediationApproval,
)


ENGINE_NAME = (
    "SS4TS AI Safe Remediation Executor"
)

ENGINE_VERSION = "1.0.0-safe-mode"


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()



def _execution_result(
    *,
    execution_id: str,
    action_type: str,
    status: str,
    message: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:

    return {

        "execution_id": execution_id,

        "action_type": action_type,

        "status": status,

        "message": message,

        "evidence": evidence,

        "executed_at": _utc_now(),

        "engine": {

            "name": ENGINE_NAME,

            "version": ENGINE_VERSION,

        },

    }



def execute_remediation(
    *,
    approval_id: str,
) -> dict[str, Any]:
    """
    H23.4.5.5.12.X.4.5.2.2.1

    Safe Remediation Executor

    Flow:

    Approval
        ↓
    Validate
        ↓
    Execute Safe Action
        ↓
    Store Result
    """


    db = SessionLocal()


    try:

        approval = (
            db.query(
                RemediationApproval
            )
            .filter(
                RemediationApproval.approval_id
                == approval_id
            )
            .first()
        )


        if not approval:

            return {

                "status": "FAILED",

                "reason":
                    "Approval request not found",

                "generated_at":
                    _utc_now(),

            }



        if approval.status != "APPROVED":

            return {

                "status":
                    "WAITING_APPROVAL",

                "approval_id":
                    approval_id,

                "message":
                    "Human approval required",

                "generated_at":
                    _utc_now(),

            }



        execution_id = str(
            uuid.uuid4()
        )


        action_type = (
            approval.action_type
        )


        #
        # SAFE MODE EXECUTION
        #
        # No MikroTik changes here.
        # Simulation only.
        #


        evidence = {

            "mode":
                "SAFE_SIMULATION",

            "router_ip":
                approval.router_ip,

            "action":
                action_type,

            "note":
                "No production change executed",

        }


        execution = RemediationExecution()

        execution.execution_id = execution_id

        execution.approval_id = approval_id

        execution.router_ip = (
            approval.router_ip
        )

        execution.action_type = action_type

        execution.status = (
            "SUCCESS"
        )

        execution.result = (
            "Safe remediation simulation completed"
        )

        execution.evidence = str(
            evidence
        )


        db.add(
            execution
        )


        db.commit()



        return _execution_result(

            execution_id=execution_id,

            action_type=action_type,

            status="SUCCESS",

            message=(
                "Safe remediation executed"
            ),

            evidence=evidence,

        )



    except Exception as exc:

        db.rollback()

        return {

            "status":
                "FAILED",

            "error":
                str(exc),

            "generated_at":
                _utc_now(),

        }


    finally:

        db.close()
