from __future__ import annotations

import re
from typing import Any

from app.events.notification_enums import EventSource, EventType


_INVALID_TOKEN_CHARACTERS = re.compile(r"[^a-zA-Z0-9_.-]+")


def _value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)

    return str(value)


def _token(value: Any) -> str:
    normalized = _value(value).strip().lower()
    normalized = _INVALID_TOKEN_CHARACTERS.sub("-", normalized)
    normalized = normalized.strip("-")

    return normalized or "unknown"


def build_notification_fingerprint(
    *,
    event_type: EventType | str,
    device_id: int | str | None = None,
    interface_id: int | str | None = None,
    metric_name: str | None = None,
    source: EventSource | str | None = None,
) -> str:
    """
    Build a stable, readable identity for event deduplication.

    The fingerprint intentionally excludes timestamps, event IDs, values,
    and messages so repeated observations map to the same incident.
    """

    parts = [_token(event_type)]

    if device_id is not None:
        parts.extend(("device", _token(device_id)))

    if interface_id is not None:
        parts.extend(("interface", _token(interface_id)))

    if metric_name:
        parts.extend(("metric", _token(metric_name)))

    if len(parts) == 1 and source is not None:
        parts.extend(("source", _token(source)))

    return ":".join(parts)
