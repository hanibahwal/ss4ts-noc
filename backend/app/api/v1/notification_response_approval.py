from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.v1.notification_security import (
    require_notification_permission,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.services.notification_response_approval import (
    NotificationResponseApprovalStore,
)

from app.services.notification_response_approval_runtime import (
    NotificationResponseApprovalRuntime,
)


router = APIRouter(
    prefix="/notifications/audit/response/approval",
    tags=[
        "notification-response-approval"
    ],
)



def get_store():

    return NotificationResponseApprovalStore(
        Path(
            "notifications.sqlite3"
        )
    )



@router.get(
    "/pending",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def pending():

    store = get_store()

    return [
        item.to_dict()
        for item in store.pending()
    ]



@router.get(
    "/latest",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def latest():

    store = get_store()

    result = store.latest()

    if not result:
        return {
            "message":
                "No approval request"
        }

    return result.to_dict()



@router.post(
    "/{approval_id}/approve",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
@router.post(
    "/{approval_id}/approve",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def approve(
    approval_id: str,
):


    runtime = (
        NotificationResponseApprovalRuntime(
            Path(
                "notifications.sqlite3"
            )
        )
    )


    result = (
        runtime.approve_and_execute(

            approval_id=approval_id,

            action_id=approval_id,

            approved_by="administrator",

        )
    )


    return result

    store = get_store()

    result = store.approve(
        approval_id,
        "administrator",
    )

    return result.to_dict()



@router.post(
    "/{approval_id}/reject",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def reject(
    approval_id: str,
):

    store = get_store()

    result = store.reject(
        approval_id,
        "administrator",
    )

    return result.to_dict()
