from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.events.notification_enums import (
    EventSeverity,
    EventSource,
    EventState,
    EventType,
)
from app.events.notification_event import (
    DeviceReference,
    InterfaceReference,
    MetricContext,
    NotificationEvent,
    SiteReference,
)


def create_notification_event(
    *,
    event_type: EventType,
    state: EventState,
    severity: EventSeverity,
    source: EventSource,
    title: str,
    message: str,
    device: DeviceReference | None = None,
    site: SiteReference | None = None,
    interface: InterfaceReference | None = None,
    metric: MetricContext | None = None,
    labels: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
    correlation_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> NotificationEvent:
    event_id = uuid4()

    event_data: dict[str, Any] = {
        "event_id": event_id,
        "correlation_id": correlation_id or event_id,
        "event_type": event_type,
        "state": state,
        "severity": severity,
        "source": source,
        "title": title,
        "message": message,
        "device": device,
        "site": site,
        "interface": interface,
        "metric": metric,
        "labels": labels or {},
        "metadata": metadata or {},
    }

    if occurred_at is not None:
        event_data["occurred_at"] = occurred_at

    return NotificationEvent.model_validate(event_data)


def create_recovery_event(
    *,
    original_event: NotificationEvent,
    event_type: EventType,
    title: str,
    message: str,
    source: EventSource | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> NotificationEvent:
    recovery_metadata = {
        "recovery_of_event_id": str(original_event.event_id),
        **(metadata or {}),
    }

    return create_notification_event(
        event_type=event_type,
        state=EventState.RECOVERED,
        severity=EventSeverity.INFO,
        source=source or original_event.source,
        title=title,
        message=message,
        device=original_event.device,
        site=original_event.site,
        interface=original_event.interface,
        metric=original_event.metric,
        labels=original_event.labels,
        metadata=recovery_metadata,
        correlation_id=original_event.correlation_id,
        occurred_at=occurred_at,
    )
