import pytest

from app.models.notification_identity import (
    NotificationIdentity,
)

from app.models.notification_permission import (
    NotificationPermission,
)

from app.services.notification_authorization import (
    NotificationAuthorizationService,
    NotificationInactiveIdentity,
    NotificationPermissionDenied,
)


def identity(
    role: str,
    active: bool = True,
):
    return NotificationIdentity(
        identity_id="user:test",
        username="tester",
        role=role,
        active=active,
    )


def test_admin_can_execute():

    result = (
        NotificationAuthorizationService()
        .authorize_execute(
            identity("ADMINISTRATOR")
        )
    )

    assert result.allowed is True



def test_requester_cannot_execute():

    with pytest.raises(
        NotificationPermissionDenied
    ):
        NotificationAuthorizationService().authorize_execute(
            identity("REQUESTER")
        )



def test_network_engineer_can_execute():

    result = (
        NotificationAuthorizationService()
        .authorize_execute(
            identity(
                "NETWORK_ENGINEER"
            )
        )
    )

    assert result.allowed



def test_inactive_identity_rejected():

    with pytest.raises(
        NotificationInactiveIdentity
    ):
        NotificationAuthorizationService().authorize_read(
            identity(
                "ADMINISTRATOR",
                active=False,
            )
        )



def test_suppression_permission():

    result = (
        NotificationAuthorizationService()
        .authorize_suppression(
            identity(
                "ADMINISTRATOR"
            )
        )
    )

    assert (
        result.permission
        == NotificationPermission.SUPPRESS
    )



def test_escalation_permission():

    result = (
        NotificationAuthorizationService()
        .authorize_escalation(
            identity(
                "SENIOR_ENGINEER"
            )
        )
    )

    assert result.allowed



def test_manage_permission():

    result = (
        NotificationAuthorizationService()
        .authorize_manage(
            identity(
                "CHANGE_MANAGER"
            )
        )
    )

    assert result.allowed



def test_unknown_role_denied():

    with pytest.raises(
        NotificationPermissionDenied
    ):
        NotificationAuthorizationService().authorize_execute(
            identity(
                "UNKNOWN"
            )
        )


def test_decision_output():

    result = (
        NotificationAuthorizationService()
        .authorize_read(
            identity(
                "REQUESTER"
            )
        )
    )

    data = result.to_dict()

    assert data["allowed"] is True
    assert (
        data["permission"]
        == "notification.read"
    )
