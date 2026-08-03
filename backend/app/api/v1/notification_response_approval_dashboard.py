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


from app.services.notification_response_approval_binding import (
    NotificationResponseApprovalBindingStore,
)



router = APIRouter(
    prefix="/notifications/audit/response/approval/dashboard",
    tags=[
        "notification-response-dashboard"
    ],
)



def get_approval_store():

    return NotificationResponseApprovalStore(
        Path(
            "notifications.sqlite3"
        )
    )



def get_binding_store():

    return NotificationResponseApprovalBindingStore(
        Path(
            "notifications.sqlite3"
        )
    )



@router.get(
    "/summary",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def summary():


    approval_store = get_approval_store()


    pending = approval_store.pending()


    return {

        "total_pending":
            len(pending),


        "high_risk":
            0,


        "medium_risk":
            0,


        "low_risk":
            len(pending),


        "approved_today":
            0,


        "rejected_today":
            0,

    }



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


    store = get_approval_store()


    return [

        item.to_dict()

        for item in store.pending()

    ]



@router.get(
    "/{approval_id}/timeline",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def timeline(
    approval_id: str,
):


    store = get_binding_store()


    events = []


    for item in store.list_history(100):

        if item.approval_id == approval_id:


            events.append(

                {

                    "type":
                        "approval",


                    "status":
                        item.status.value,


                    "timestamp":
                        item.created_at.isoformat(),

                }

            )


    return {

        "approval_id":
            approval_id,


        "events":
            events,

    }
