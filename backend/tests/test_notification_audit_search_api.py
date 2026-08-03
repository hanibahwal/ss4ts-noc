from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

from app.services.notification_audit import (
    NotificationAuditStore,
)

from app.models.notification_audit import (
    NotificationAuditAction,
    NotificationAuditResult,
)


client = TestClient(app)



def create_test_audits():

    store = NotificationAuditStore(
        Path(
            "notifications.sqlite3"
        )
    )


    store.create_audit(
        identity_id="admin",
        action=NotificationAuditAction.READ,
        result=NotificationAuditResult.SUCCESS,
        resource="notification",
        message="read event",
    )


    store.create_audit(
        identity_id="admin",
        action=NotificationAuditAction.EXECUTE,
        result=NotificationAuditResult.SUCCESS,
        resource="pipeline",
        message="execute event",
    )


    store.create_audit(
        identity_id="user1",
        action=NotificationAuditAction.READ,
        result=NotificationAuditResult.DENIED,
        resource="notification",
        message="denied event",
    )



def test_search_audit_without_filter():

    create_test_audits()


    response = client.get(
        "/api/v1/notifications/audit/search"
    )


    assert response.status_code == 200


    data = response.json()


    assert "items" in data

    assert data["count"] >= 3




def test_search_by_identity():

    response = client.get(
        "/api/v1/notifications/audit/search",
        params={
            "identity_id": "admin"
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert all(
        item["identity_id"]
        == "admin"
        for item in data["items"]
    )




def test_search_by_action():

    response = client.get(
        "/api/v1/notifications/audit/search",
        params={
            "action": "execute"
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert all(
        item["action"]
        == "execute"
        for item in data["items"]
    )




def test_search_pagination():

    response = client.get(
        "/api/v1/notifications/audit/search",
        params={
            "limit": 1,
            "offset": 0,
        },
    )


    assert response.status_code == 200


    data = response.json()


    assert data["limit"] == 1

    assert data["offset"] == 0
