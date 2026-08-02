from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

from app.models.notification import (
    NotificationIncident,
    NotificationIncidentStatus,
)

from app.services.notification_store import (
    NotificationStore,
)


client = TestClient(app)


def create_test_incident() -> None:

    store = NotificationStore(
        Path(
            "notifications.sqlite3"
        )
    )

    incident = NotificationIncident(
        incident_id="inc-001",
        fingerprint="security-test-inc-001",
        correlation_id="security-test-inc-001",
        event_type="notification",
        severity="warning",
        status=NotificationIncidentStatus.OPEN,
        title="Security Test Incident",
        message="Security validation incident",
        device_id=None,
        site_id=None,
    )

    try:
        store.create_incident(
            incident
        )

    except Exception:
        pass


def test_pipeline_endpoint_authorized():

    create_test_incident()

    response = client.post(
        "/api/v1/notifications/pipeline",
        json={
            "incident_id": "inc-001",
            "channel": "dashboard",
            "destination": "noc",
            "body": "test notification",
        },
    )

    assert response.status_code == 200


def test_delivery_read_authorized():

    response = client.get(
        "/api/v1/notifications/deliveries"
    )

    assert response.status_code == 200


def test_delivery_not_found_with_security():

    response = client.get(
        "/api/v1/notifications/deliveries/not-found"
    )

    assert response.status_code == 404


def test_health_without_permission():

    response = client.get(
        "/api/v1/notifications/health"
    )

    assert response.status_code == 200
