from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

import pytest

from app.services.autonomous_authorization_intent_audit import (
    AutonomousAuthorizationIntentAuditReport,
    verify_autonomous_authorization_intent_store,
)
from app.services.autonomous_authorization_intent_store import (
    AutonomousAuthorizationIntentStore,
)
from tests.test_autonomous_authorization_intent_store import (
    make_intent,
)


NOW = datetime(
    2026,
    8,
    6,
    21,
    45,
    tzinfo=timezone.utc,
)


def test_verify_empty_store(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    report = (
        verify_autonomous_authorization_intent_store(
            store,
            audit_id=(
                "autonomous-authorization-intent-audit:"
                "empty"
            ),
            audited_at=NOW,
        )
    )

    assert isinstance(
        report,
        AutonomousAuthorizationIntentAuditReport,
    )

    assert report.record_count == 0
    assert report.verified_record_count == 0
    assert report.first_sequence_number is None
    assert report.last_sequence_number is None
    assert report.audit_valid is True
    assert report.can_execute is False


def test_verify_valid_store(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path
    )

    store.append(
        intent=intent
    )

    report = (
        verify_autonomous_authorization_intent_store(
            store,
            audit_id=(
                "autonomous-authorization-intent-audit:"
                "valid"
            ),
            audited_at=NOW,
        )
    )

    assert report.record_count == 1
    assert report.verified_record_count == 1
    assert report.first_sequence_number == 1
    assert report.last_sequence_number == 1

    assert report.record_hashes_valid is True
    assert report.hash_chain_valid is True

    assert (
        report.bridge_fingerprints_valid
        is True
    )

    assert (
        report.request_bindings_valid
        is True
    )

    assert (
        report.request_audits_valid
        is True
    )

    assert report.safety_claims_valid is True
    assert report.audit_valid is True


def test_report_is_never_executable(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    report = (
        verify_autonomous_authorization_intent_store(
            store
        )
    )

    assert (
        report.execution_authorization_created
        is False
    )

    assert report.execution_allowed is False
    assert report.can_execute is False


def test_report_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    payload = (
        verify_autonomous_authorization_intent_store(
            store,
            audited_at=NOW,
        ).to_dict()
    )

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "authorization_intent_audit_only": True,
        "intent_store_read_only": True,
        "execution_authorization_created": False,
        "execution_authorization_stored": False,
        "authorization_approved": False,
        "authorization_token_created": False,
        "approval_claim_created": False,
        "execution_lease_created": False,
        "execution_allowed": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_access_performed": False,
        "command_generated": False,
        "device_command_executed": False,
    }


def test_tampered_record_is_invalid(
    tmp_path,
) -> None:
    database = tmp_path / "intents.db"

    store = AutonomousAuthorizationIntentStore(
        database
    )

    store.append(
        intent=make_intent(
            tmp_path
        )
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_authorization_intent_records
            SET record_hash = ?
            """,
            (
                "f" * 64,
            ),
        )

        connection.commit()

    report = (
        verify_autonomous_authorization_intent_store(
            store
        )
    )

    assert report.audit_valid is False
    assert report.record_hashes_valid is False
    assert report.hash_chain_valid is False


def test_tampered_payload_is_invalid(
    tmp_path,
) -> None:
    database = tmp_path / "intents.db"

    store = AutonomousAuthorizationIntentStore(
        database
    )

    store.append(
        intent=make_intent(
            tmp_path
        )
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_authorization_intent_records
            SET intent_payload = ?
            """,
            (
                '{"can_execute": true}',
            ),
        )

        connection.commit()

    report = (
        verify_autonomous_authorization_intent_store(
            store
        )
    )

    assert report.audit_valid is False
    assert report.safety_claims_valid is False


def test_invalid_store_type_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="AutonomousAuthorizationIntentStore",
    ):
        verify_autonomous_authorization_intent_store(
            "invalid"
        )


def test_empty_audit_id_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    with pytest.raises(
        ValueError,
        match="audit_id",
    ):
        verify_autonomous_authorization_intent_store(
            store,
            audit_id=" ",
        )
