from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends


from app.api.v1.notification_security import (
    require_notification_permission,
)


from app.models.notification_permission import (
    NotificationPermission,
)


from app.services.notification_response_execution_runtime import (
    NotificationResponseExecutionRuntime,
)


from app.services.notification_response_execution_history import (
    NotificationResponseExecutionHistoryStore,
)



router = APIRouter(
    prefix="/notifications/audit/response",
    tags=[
        "notification-response"
    ],
)



def get_runtime():

    return NotificationResponseExecutionRuntime(
        Path(
            "notifications.sqlite3"
        )
    )



def get_history_store():

    return NotificationResponseExecutionHistoryStore(
        Path(
            "notifications.sqlite3"
        )
    )




@router.post(
    "/run",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def run_response():


    runtime = get_runtime()


    return runtime.execute()




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
def latest_response():


    store = get_history_store()


    result = store.latest()



    if not result:

        return {
            "message":
                "No execution history"
        }



    return result.to_dict()




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
def response_history(
    limit:int = 50,
):


    store = get_history_store()



    return [

        item.to_dict()

        for item in store.list_history(
            limit
        )

    ]
