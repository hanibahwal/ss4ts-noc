from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from app.services.autonomous_authorization_intent_store import (
    AutonomousAuthorizationIntentStore,
)
from app.services.autonomous_authorization_request_store import (
    AutonomousAuthorizationRequestDuplicate,
    AutonomousAuthorizationRequestStore,
)
from app.services.autonomous_controlled_authorization_integration import (
    AutonomousControlledAuthorizationIntegration,
    AutonomousControlledAuthorizationIntegrationResult,
    integrate_controlled_authorization,
)
from tests.test_autonomous_authorization_request_store import (
    make_request,
)


NOW = datetime(
    2026,
    8,
    6,
    21,
    50,
    tzinfo=timezone.utc,
)


def make_integration(
    tmp_path,
):
    request_store = (
        AutonomousAuthorizationRequestStore(
            tmp_path / "requests.db"
        )
    )

    intent_store = (
        AutonomousAuthorizationIntentStore(
            tmp_path / "intents.db"
        )
    )

    integration = (
        AutonomousControlledAuthorizationIntegration(
            request_store=request_store,
            intent_store=intent_store,
        )
    )

    return (
        integration,
        request_store,
        intent_store,
    )


def test_complete_controlled_authorization_flow(
    tmp_path,
) -> None:
    (
        integration,
        request_store,
        intent_store,
    ) = make_integration(
        tmp_path
    )

    result = integration.integrate(
        request=make_request(
            tmp_path
        ),
        integration_id=(
            "autonomous-controlled-authorization-"
            "integration:test"
        ),
        authorization_intent_id=(
            "autonomous-authorization-intent:"
            "integration-test"
        ),
        integrated_at=NOW,
    )

    assert isinstance(
        result,
        AutonomousControlledAuthorizationIntegrationResult,
    )

    assert result.integration_valid is True

    assert (
        result.request_record.authorization_request_id
        == result.authorization_intent.authorization_request_id
    )

    assert (
        result.request_record.record_hash
        == result.authorization_intent.request_record_hash
    )

    assert (
        result.request_audit.audit_id
        == result.authorization_intent.request_audit_id
    )

    assert (
        result.authorization_intent.authorization_intent_id
        == result.intent_record.authorization_intent_id
    )

    assert (
        result.authorization_intent.bridge_fingerprint
        == result.intent_record.bridge_fingerprint
    )

    assert request_store.count() == 1
    assert intent_store.count() == 1

    assert result.request_audit.audit_valid is True
    assert result.intent_audit.audit_valid is True


def test_functional_integration_entrypoint(
    tmp_path,
) -> None:
    request_store = (
        AutonomousAuthorizationRequestStore(
            tmp_path / "requests.db"
        )
    )

    intent_store = (
        AutonomousAuthorizationIntentStore(
            tmp_path / "intents.db"
        )
    )

    result = integrate_controlled_authorization(
        request=make_request(
            tmp_path
        ),
        request_store=request_store,
        intent_store=intent_store,
        integrated_at=NOW,
    )

    assert result.integration_valid is True
    assert result.can_execute is False


def test_result_is_never_executable(
    tmp_path,
) -> None:
    integration, _, _ = make_integration(
        tmp_path
    )

    result = integration.integrate(
        request=make_request(
            tmp_path
        ),
        integrated_at=NOW,
    )

    assert (
        result.execution_authorization_created
        is False
    )

    assert result.authorization_approved is False

    assert (
        result.authorization_token_created
        is False
    )

    assert result.approval_claim_created is False
    assert result.execution_lease_created is False
    assert result.execution_allowed is False
    assert result.can_execute is False


def test_result_safety_metadata(
    tmp_path,
) -> None:
    integration, _, _ = make_integration(
        tmp_path
    )

    payload = integration.integrate(
        request=make_request(
            tmp_path
        ),
        integrated_at=NOW,
    ).to_dict()

    assert payload["integration_valid"] is True
    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "controlled_authorization_integration_only":
            True,
        "request_store_append_only":
            True,
        "intent_store_append_only":
            True,
        "execution_authorization_created":
            False,
        "execution_authorization_stored":
            False,
        "authorization_approved":
            False,
        "authorization_token_created":
            False,
        "approval_claim_created":
            False,
        "execution_lease_created":
            False,
        "execution_allowed":
            False,
        "execution_approved":
            False,
        "simulation_started":
            False,
        "network_io_performed":
            False,
        "device_access_performed":
            False,
        "command_generated":
            False,
        "device_command_executed":
            False,
    }


def test_duplicate_request_rejected(
    tmp_path,
) -> None:
    integration, _, _ = make_integration(
        tmp_path
    )

    request = make_request(
        tmp_path
    )

    integration.integrate(
        request=request,
        integrated_at=NOW,
    )

    with pytest.raises(
        AutonomousAuthorizationRequestDuplicate,
    ):
        integration.integrate(
            request=request,
            integrated_at=NOW,
        )


def test_invalid_request_type_rejected(
    tmp_path,
) -> None:
    integration, _, _ = make_integration(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="AutonomousControlledAuthorizationRequest",
    ):
        integration.integrate(
            request={},
        )


def test_invalid_store_types_rejected(
    tmp_path,
) -> None:
    request_store = (
        AutonomousAuthorizationRequestStore(
            tmp_path / "requests.db"
        )
    )

    intent_store = (
        AutonomousAuthorizationIntentStore(
            tmp_path / "intents.db"
        )
    )

    with pytest.raises(
        TypeError,
        match="request_store",
    ):
        AutonomousControlledAuthorizationIntegration(
            request_store="invalid",
            intent_store=intent_store,
        )

    with pytest.raises(
        TypeError,
        match="intent_store",
    ):
        AutonomousControlledAuthorizationIntegration(
            request_store=request_store,
            intent_store="invalid",
        )


def test_empty_integration_id_rejected(
    tmp_path,
) -> None:
    integration, request_store, intent_store = (
        make_integration(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="integration_id",
    ):
        integration.integrate(
            request=make_request(
                tmp_path
            ),
            integration_id=" ",
        )

    assert request_store.count() == 0
    assert intent_store.count() == 0


def test_tampered_request_store_blocks_integration(
    tmp_path,
) -> None:
    request_database = (
        tmp_path / "requests.db"
    )

    request_store = (
        AutonomousAuthorizationRequestStore(
            request_database
        )
    )

    intent_store = (
        AutonomousAuthorizationIntentStore(
            tmp_path / "intents.db"
        )
    )

    request_store.append(
        request=make_request(
            tmp_path
        )
    )

    with sqlite3.connect(
        request_database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_authorization_request_records
            SET record_hash = ?
            """,
            (
                "f" * 64,
            ),
        )

        connection.commit()

    integration = (
        AutonomousControlledAuthorizationIntegration(
            request_store=request_store,
            intent_store=intent_store,
        )
    )

    with pytest.raises(
        Exception,
    ):
        integration.integrate(
            request=make_request(
                tmp_path / "next"
            ),
            integrated_at=NOW,
        )

    assert intent_store.count() == 0
