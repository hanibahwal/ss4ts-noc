from fastapi import APIRouter

from app.services.remediation_approval_service import (
    approve_remediation,
    reject_remediation,
)


router = APIRouter(
    prefix="/remediation",
    tags=["Remediation Approval"],
)



@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
):

    return approve_remediation(
        approval_id
    )



@router.post("/{approval_id}/reject")
def reject(
    approval_id: str,
):

    return reject_remediation(
        approval_id
    )
