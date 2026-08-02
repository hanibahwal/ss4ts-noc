from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.events import (
    DeviceReference,
    EventSeverity,
    EventSource,
    EventState,
    EventType,
    InterfaceReference,
    MetricContext,
    NotificationEvent,
    SiteReference,
    create_notification_event,
    create_recovery_event,
    notification_event_json_schema,
)


def make_device() -> DeviceReference:
    return DeviceReference(
        id=25,
        name="AFURAH-CAMP-RTR-01",
        hostname="afurah-core",
        ip="10.10.10.1",
        role="core-router",
        vendor="MikroTik",
        model="CCR2116",
    )


def test_factory_creates_valid_device_event() -> None:
    event = create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=EventState.FIRING,
        severity=EventSeverity.CRITICAL,
        source=EventSource.PING_MONITOR,
        title="Device unreachable",
        message="Ping failed for 60 seconds",
        device=make_device(),
        site=SiteReference(
            id=4,
            name="Al-Jafurah",
            region="Eastern",
        ),
        labels={
            "environment": "production",
            "service": "internet",
        },
        metadata={
            "failed_probes": 3,
        },
    )

    assert isinstance(event.event_id, UUID)
    assert event.correlation_id == event.event_id
    assert event.fingerprint == "device_down:device:25"
    assert event.occurred_at.tzinfo is timezone.utc
    assert event.created_at.tzinfo is timezone.utc


def test_metric_is_part_of_fingerprint() -> None:
    event = create_notification_event(
        event_type=EventType.HIGH_CPU,
        state=EventState.FIRING,
        severity=EventSeverity.MAJOR,
        source=EventSource.SNMP_MONITOR,
        title="High CPU usage",
        message="CPU remained above 90 percent",
        device=make_device(),
        metric=MetricContext(
            name="cpu_usage",
            value=96.5,
            threshold=90,
            unit="percent",
        ),
    )

    assert (
        event.fingerprint
        == "high_cpu:device:25:metric:cpu_usage"
    )


def test_interface_event_requires_interface() -> None:
    with pytest.raises(
        ValidationError,
        match="requires an interface",
    ):
        create_notification_event(
            event_type=EventType.INTERFACE_DOWN,
            state=EventState.FIRING,
            severity=EventSeverity.MAJOR,
            source=EventSource.SNMP_MONITOR,
            title="Interface down",
            message="ether10 changed to down",
            device=make_device(),
        )


def test_interface_fingerprint_is_stable() -> None:
    interface = InterfaceReference(
        id="ether10",
        name="ether10-TO-WAN",
    )

    first = create_notification_event(
        event_type=EventType.INTERFACE_DOWN,
        state=EventState.FIRING,
        severity=EventSeverity.MAJOR,
        source=EventSource.SNMP_MONITOR,
        title="Interface down",
        message="First observation",
        device=make_device(),
        interface=interface,
    )

    second = create_notification_event(
        event_type=EventType.INTERFACE_DOWN,
        state=EventState.ACTIVE,
        severity=EventSeverity.MAJOR,
        source=EventSource.SNMP_MONITOR,
        title="Interface still down",
        message="Second observation",
        device=make_device(),
        interface=interface,
    )

    assert first.event_id != second.event_id
    assert first.fingerprint == second.fingerprint
    assert (
        first.fingerprint
        == "interface_down:device:25:interface:ether10"
    )


def test_recovery_event_preserves_correlation() -> None:
    firing = create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=EventState.FIRING,
        severity=EventSeverity.CRITICAL,
        source=EventSource.PING_MONITOR,
        title="Device unreachable",
        message="Device is down",
        device=make_device(),
    )

    recovery = create_recovery_event(
        original_event=firing,
        event_type=EventType.DEVICE_UP,
        title="Device recovered",
        message="Device is reachable again",
    )

    assert recovery.event_id != firing.event_id
    assert recovery.correlation_id == firing.correlation_id
    assert recovery.state is EventState.RECOVERED
    assert recovery.severity is EventSeverity.INFO
    assert (
        recovery.metadata["recovery_of_event_id"]
        == str(firing.event_id)
    )


def test_event_is_immutable() -> None:
    event = create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=EventState.FIRING,
        severity=EventSeverity.CRITICAL,
        source=EventSource.PING_MONITOR,
        title="Device unreachable",
        message="Device is down",
        device=make_device(),
    )

    with pytest.raises(ValidationError):
        event.title = "Changed title"


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        create_notification_event(
            event_type=EventType.DEVICE_DOWN,
            state=EventState.FIRING,
            severity=EventSeverity.CRITICAL,
            source=EventSource.PING_MONITOR,
            title="Device unreachable",
            message="Device is down",
            device=make_device(),
            occurred_at=datetime(2026, 8, 2, 18, 15),
        )


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        NotificationEvent.model_validate(
            {
                "event_type": "service_started",
                "state": "firing",
                "severity": "info",
                "source": "system",
                "title": "Service started",
                "message": "Notification worker started",
                "unexpected": "not allowed",
            }
        )


def test_payload_is_json_serializable() -> None:
    event = create_notification_event(
        event_type=EventType.DEVICE_DOWN,
        state=EventState.FIRING,
        severity=EventSeverity.CRITICAL,
        source=EventSource.PING_MONITOR,
        title="Device unreachable",
        message="Device is down",
        device=make_device(),
    )

    payload = event.to_payload()

    assert payload["schema_version"] == "1.0"
    assert payload["event_type"] == "device_down"
    assert payload["state"] == "firing"
    assert isinstance(payload["event_id"], str)
    assert payload["occurred_at"].endswith("Z")


def test_json_schema_exposes_required_contract_fields() -> None:
    schema = notification_event_json_schema()
    properties = schema["properties"]
    required = set(schema["required"])

    assert "event_id" in properties
    assert "correlation_id" in properties
    assert "fingerprint" in properties
    assert "event_type" in required
    assert "state" in required
    assert "severity" in required
    assert "source" in required
    assert "title" in required
    assert "message" in required
