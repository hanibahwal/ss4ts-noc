from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.v1.notification_security import (
    require_notification_permission,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.services.notification_audit_decision_history import (
    NotificationDecisionHistoryStore,
)

from app.services.notification_audit_decision_runtime import (
    NotificationDecisionRuntime,
)



router = APIRouter(
    prefix="/notifications/audit/decision",
    tags=[
        "notification-audit-decision-history"
    ],
)



def get_history_store():

    return NotificationDecisionHistoryStore(
        Path(
            "notifications.sqlite3"
        )
    )



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
def latest_decision():

    store = get_history_store()

    result = store.latest()

    if not result:
        return {
            "message":
                "No decision history available"
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
def decision_history(
    limit: int = 50,
):

    store = get_history_store()

    return [
        item.to_dict()
        for item in store.list_history(
            limit
        )
    ]



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
def run_decision():

    runtime = NotificationDecisionRuntime(
        Path(
            "notifications.sqlite3"
        )
    )

    result = runtime.execute()

    return result.to_dict()
