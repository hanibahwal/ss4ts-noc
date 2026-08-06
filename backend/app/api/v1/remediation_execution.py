from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Any


from app.services.remediation_approval_service import (
    get_pending_approvals,
    approve_remediation,
)


from app.services.controlled_execution_gate import (
    execute_controlled_remediation,
)
from app.services.controlled_execution_receipt_store import (
    receipt_store,
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
) -> dict[str, Any]:
    """
    Execute approved remediation.
    """


    result = execute_controlled_remediation(
        approval_id=approval_id,
    )


    return result

@router.get(
    "/executions/{execution_id}/receipt"
)
def execution_receipt(
    execution_id: str,
) -> dict[str, Any]:
    try:
        receipt = receipt_store.get(
            execution_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if receipt is None:
        raise HTTPException(
            status_code=404,
            detail="Execution receipt not found",
        )

    return {
        "receipt": receipt.to_dict(),
    }


@router.get(
    "/{approval_id}/execution-receipts"
)
def approval_execution_receipts(
    approval_id: str,
    limit: int = 50,
) -> dict[str, Any]:
    try:
        receipts = (
            receipt_store.by_approval(
                approval_id,
                limit=limit,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return {
        "approval_id": approval_id,
        "count": len(receipts),
        "receipts": [
            receipt.to_dict()
            for receipt in receipts
        ],
    }

