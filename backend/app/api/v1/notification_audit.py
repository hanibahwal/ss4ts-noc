from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.api.v1.notification_security import (
    require_notification_permission,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.services.notification_audit import (
    NotificationAuditStore,
)


router = APIRouter(
    prefix="/notifications/audit",
    tags=["notification-audit"],
)


def get_audit_store() -> NotificationAuditStore:

    return NotificationAuditStore(
        Path(
            "notifications.sqlite3"
        )
    )


@router.get(
    "",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def list_audit_records() -> list[dict]:

    store = get_audit_store()

    return [
        item.to_dict()
        for item in store.list_audits()
    ]



# =====================================================
# H23.4.5.5.12.16
# Notification Audit Query & Filtering Engine
#
# Single Audit Record Lookup
#
# Old:
# /notifications/audit/{audit_id}
#
# New:
# /notifications/audit/id/{audit_id}
#
# To avoid conflict with:
# /notifications/audit/search
# =====================================================


@router.get(
    "/id/{audit_id}",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def get_audit_record(
    audit_id: str,
) -> dict:

    store = get_audit_store()

    record = store.get_audit(
        audit_id
    )

    if record is None:

        raise HTTPException(
            status_code=404,
            detail="Audit record not found",
        )

    return record.to_dict()
