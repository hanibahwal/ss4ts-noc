from __future__ import annotations

from typing import Any

from app.events.notification_event import NotificationEvent


def notification_event_json_schema() -> dict[str, Any]:
    """
    Return the canonical JSON Schema for integrations and documentation.
    """

    return NotificationEvent.model_json_schema()
