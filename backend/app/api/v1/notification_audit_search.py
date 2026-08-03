from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from app.api.v1.notification_security import (
    require_notification_permission,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.models.notification_audit import (
    NotificationAuditAction,
    NotificationAuditResult,
)

from app.models.notification_audit_query import (
    NotificationAuditQuery,
)

from app.services.notification_audit import (
    NotificationAuditStore,
)


router = APIRouter(
    prefix="/notifications/audit",
    tags=["notification-audit-search"],
)


def get_audit_store():

    return NotificationAuditStore(
        Path(
            "notifications.sqlite3"
        )
    )



@router.get(
    "/search",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def search_audit_records(
    identity_id: str | None = None,

    action: NotificationAuditAction | None = None,

    result: NotificationAuditResult | None = None,

    resource: str | None = None,

    resource_id: str | None = None,

    from_date: datetime | None = None,

    to_date: datetime | None = None,

    limit: int = Query(
        50,
        ge=1,
        le=500,
    ),

    offset: int = Query(
        0,
        ge=0,
    ),

):

    store = get_audit_store()


    query = NotificationAuditQuery(

        identity_id=identity_id,

        action=action,

        result=result,

        resource=resource,

        resource_id=resource_id,

        from_date=from_date,

        to_date=to_date,

        limit=limit,

        offset=offset,
    )


    records = store.query_audits(
        query
    )


    return {
        "count": len(records),

        "limit": limit,

        "offset": offset,

        "items": [
            item.to_dict()
            for item in records
        ],
    }
