from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_notification_health():

    response = client.get(
        "/api/v1/notifications/health"
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["service"]
        == "notification"
    )


def test_pipeline_validation():

    response = client.post(
        "/api/v1/notifications/pipeline",
        json={},
    )

    assert response.status_code == 422


def test_delivery_not_found():

    response = client.get(
        "/api/v1/notifications/deliveries/nope"
    )

    assert response.status_code in {
        404,
        500,
    }
