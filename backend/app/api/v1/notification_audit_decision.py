from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

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

from app.services.notification_audit_decision import (
    NotificationAuditDecisionEngine,
)



router = APIRouter(
    prefix="/notifications/audit",
    tags=[
        "notification-audit-decision"
    ],
)



def get_decision_engine():

    store = NotificationAuditStore(
        Path(
            "notifications.sqlite3"
        )
    )


    risk_engine = (
        NotificationAuditIntelligence(
            store
        )
    )


    decision_engine = (
        NotificationAuditDecisionEngine()
    )


    return (
        risk_engine,
        decision_engine,
    )



@router.get(
    "/decision",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def notification_audit_decision():

    risk_engine, decision_engine = (
        get_decision_engine()
    )


    risk = (
        risk_engine.calculate()
    )


    decision = (
        decision_engine.calculate(
            risk
        )
    )


    return decision.to_dict()
