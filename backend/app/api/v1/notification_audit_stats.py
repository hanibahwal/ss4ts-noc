from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
)

from app.api.v1.notification_security import (
    require_notification_permission,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.services.notification_audit_analytics import (
    NotificationAuditAnalytics,
)


router = APIRouter(
    prefix="/notifications/audit",
    tags=["notification-audit-stats"],
)


def get_analytics():

    return NotificationAuditAnalytics()



@router.get(
    "/stats",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def audit_statistics():

    analytics = get_analytics()

    stats = analytics.generate_stats()

    return stats.to_dict()
