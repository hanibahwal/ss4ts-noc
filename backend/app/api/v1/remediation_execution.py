from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Any


from app.services.remediation_approval_service import (
    get_pending_approvals,
    approve_remediation,
)


from app.services.autonomous_remediation_controller import (
    execute_approved_remediation,
)


router = APIRouter(
    prefix="/remediation",
    tags=["remediation"],
)



@router.get(
    "/pending"
)
def pending_remediations() -> dict[str, Any]:
    """
    Get waiting human approvals.
    """

    return {

        "status": "SUCCESS",

        "count": len(
            get_pending_approvals()
        ),

        "approvals": (
            get_pending_approvals()
        ),

    }




@router.post(
    "/{approval_id}/approve"
)
def approve(
    approval_id: str,
) -> dict[str, Any]:
    """
    Human approval action.
    """

    result = approve_remediation(
        approval_id=approval_id,
        approved_by="NOC_OPERATOR",
    )


    if not result.get(
        "success"
    ):

        raise HTTPException(
            status_code=404,
            detail="Approval request not found",
        )


    return result




@router.post(
    "/{approval_id}/execute"
)
def execute(
    approval_id: str,
    router_ip: str,
    action_type: str,
) -> dict[str, Any]:
    """
    Execute approved remediation.
    """


    result = execute_approved_remediation(
        approval_id=approval_id,
        router_ip=router_ip,
        action_type=action_type,
    )


    return result
