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


from app.services.notification_response_approval_binding import (
    NotificationResponseApprovalBindingStore,
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





def get_binding_store():

    return NotificationResponseApprovalBindingStore(
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
def approve(
    approval_id: str,
):


    runtime = NotificationResponseApprovalRuntime(
        Path(
            "notifications.sqlite3"
        )
    )


    result = runtime.approve_and_execute(

        approval_id=approval_id,

        action_id=approval_id,

        approved_by="administrator",

    )


    return result







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







# =====================================================
# H23.4.5.5.12.22.8.1
# Approval Binding History
# =====================================================


@router.get(
    "/history",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def history(
    limit: int = 50,
):


    store = get_binding_store()



    return [

        item.to_dict()

        for item in store.list_history(
            limit
        )

    ]








@router.get(
    "/binding/{binding_id}",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def binding_details(
    binding_id: str,
):


    store = get_binding_store()



    items = store.list_history(
        100
    )



    for item in items:


        if item.binding_id == binding_id:


            return item.to_dict()



    return {

        "message":

            "Binding not found"

    }
