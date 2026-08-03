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

from app.services.notification_audit import (
    NotificationAuditStore,
)

from app.services.notification_audit_intelligence import (
    NotificationAuditIntelligence,
)



router = APIRouter(
    prefix="/notifications/audit",
    tags=[
        "notification-audit-intelligence"
    ],
)



def get_intelligence_service():

    store = NotificationAuditStore(
        Path(
            "notifications.sqlite3"
        )
    )

    return NotificationAuditIntelligence(
        store
    )



@router.get(
    "/intelligence",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def audit_intelligence():

    engine = (
        get_intelligence_service()
    )

    result = (
        engine.calculate()
    )

    return result.to_dict()
