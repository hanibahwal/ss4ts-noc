from fastapi.testclient import TestClient

from app.main import app

from app.services.notification_audit import (
    NotificationAuditStore,
)

from app.models.notification_audit import (
    NotificationAuditAction,
    NotificationAuditResult,
)

from pathlib import Path


client = TestClient(app)


def create_test_audit():

    store = NotificationAuditStore(
        Path(
            "notifications.sqlite3"
        )
    )

    return store.create_audit(
        identity_id="user:test",
        action=NotificationAuditAction.READ,
        result=NotificationAuditResult.SUCCESS,
        resource="notification",
        message="audit api test",
    )


def test_list_audit_authorized():

    create_test_audit()

    response = client.get(
        "/api/v1/notifications/audit"
    )

    assert response.status_code == 200

    assert isinstance(
        response.json(),
        list,
    )


def test_get_audit_authorized():

    record = create_test_audit()

    response = client.get(
        f"/api/v1/notifications/audit/{record.audit_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["audit_id"]
        == record.audit_id
    )


def test_audit_not_found():

    response = client.get(
        "/api/v1/notifications/audit/not-found"
    )

    assert response.status_code == 404
