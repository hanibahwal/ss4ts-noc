from __future__ import annotations

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

from app.services.notification_audit import (
    NotificationAuditStore,
)

from app.services.notification_audit_timeline import (
    NotificationAuditTimelineAnalytics,
)


router = APIRouter(
    prefix="/notifications/audit",
    tags=["notification-audit-timeline"],
)


def get_timeline_service():

    store = NotificationAuditStore(
        Path(
            "notifications.sqlite3"
        )
    )

    return NotificationAuditTimelineAnalytics(
        store
    )


@router.get(
    "/timeline",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def audit_timeline(
    period: str = Query(
        "hour",
        pattern="^(hour|day)$",
    ),
):

    analytics = (
        get_timeline_service()
    )

    timeline = analytics.generate(
        period=period
    )

    return timeline.to_dict()
