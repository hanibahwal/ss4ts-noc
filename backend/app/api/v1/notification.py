from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import BaseModel

from app.api.v1.notification_security import (
    require_notification_permission,
)

from app.models.notification import (
    NotificationChannel,
    NotificationType,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.models.notification_deduplication import (
    DeduplicationContext,
)

from app.models.notification_pipeline import (
    NotificationPipelineRequest,
)

from app.models.notification_suppression_engine import (
    NotificationSuppressionContext,
)

from app.services.notification_pipeline import (
    NotificationPipeline,
)

from app.services.notification_store import (
    NotificationStore,
)


router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
)


def get_store() -> NotificationStore:
    return NotificationStore(
        Path(
            "notifications.sqlite3"
        )
    )


class PipelineRequest(BaseModel):
    incident_id: str

    policy_id: str | None = None

    channel: NotificationChannel

    destination: str

    subject: str = "Notification"

    body: str

    severity: str = "warning"

    site_id: str | None = None

    device_id: str | None = None

    force: bool = False


class SuppressionRequest(BaseModel):
    name: str

    reason: str

    kind: str = "manual"

    starts_at: datetime

    ends_at: datetime


@router.get("/health")
def notification_health() -> dict[str, Any]:
    return {
        "service": "notification",
        "status": "healthy",
        "pipeline": True,
    }


@router.post(
    "/pipeline",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.EXECUTE
            )
        )
    ],
)
def execute_pipeline(
    request: PipelineRequest,
) -> dict[str, Any]:

    store = get_store()

    pipeline_request = NotificationPipelineRequest(
        incident_id=request.incident_id,
        policy_id=request.policy_id,
        channel=request.channel,
        destination=request.destination,
        subject=request.subject,
        body=request.body,
        notification_type=(
            NotificationType.FIRING
        ),
        deduplication_context=(
            DeduplicationContext(
                incident_id=request.incident_id,
                policy_id=request.policy_id,
                notification_type="firing",
                current_severity=request.severity,
                cooldown_seconds=900,
                force=request.force,
            )
        ),
        suppression_context=(
            NotificationSuppressionContext(
                event_type="notification",
                evaluated_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
                site_id=request.site_id,
                device_id=request.device_id,
                severity=request.severity,
                force=request.force,
            )
        ),
    )

    result = NotificationPipeline(
        store,
        dispatcher=None,
    ).execute(
        pipeline_request
    )

    return {
        "status": result.status.value,
        "reason": result.reason,
        "successful": result.successful,
    }


@router.get(
    "/deliveries",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def list_deliveries() -> list[dict]:

    store = get_store()

    return [
        asdict(item)
        for item in store.list_deliveries()
    ]


@router.get(
    "/deliveries/{delivery_id}",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def delivery_detail(
    delivery_id: str,
) -> dict:

    store = get_store()

    delivery = store.get_delivery(
        delivery_id
    )

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found",
        )

    return asdict(delivery)


@router.get(
    "/suppressions",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def list_suppressions() -> list[dict]:

    store = get_store()

    return [
        asdict(item)
        for item in store.list_active_suppressions()
    ]
