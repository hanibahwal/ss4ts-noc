from __future__ import annotations

import json
import sqlite3

import pytest

from app.services.autonomous_authorization_request_audit import (
    AutonomousAuthorizationRequestAuditVerifier,
    verify_autonomous_authorization_request_store,
)
from app.services.autonomous_authorization_request_store import (
    AutonomousAuthorizationRequestStore,
)
from tests.test_autonomous_authorization_request_store import (
    make_request,
)


TABLE = (
    "autonomous_authorization_request_records"
)


def append_request(
    store,
    tmp_path,
    *,
    number: int = 1,
):
    return store.append(
        request=make_request(
            tmp_path,
            number=number,
        )
    )


def update_database(
    database,
    sql,
    parameters=(),
) -> None:
    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            sql,
            parameters,
        )
        connection.commit()


def load_payload(
    database,
    *,
    sequence_number: int = 1,
):
    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT request_payload
            FROM {TABLE}
            WHERE sequence_number = ?
            """,
            (
                sequence_number,
            ),
        ).fetchone()

    return json.loads(
        row[0]
    )


def update_payload(
    database,
    payload,
    *,
    sequence_number: int = 1,
) -> None:
    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET request_payload = ?
        WHERE sequence_number = ?
        """,
        (
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ),
            sequence_number,
        ),
    )


def test_valid_request_store_audit(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    append_request(
        store,
        tmp_path,
        number=1,
    )

    append_request(
        store,
        tmp_path,
        number=2,
    )

    report = (
        verify_autonomous_authorization_request_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 2
    assert report.verified_record_count == 2
    assert report.first_sequence_number == 1
    assert report.last_sequence_number == 2
    assert report.can_execute is False


def test_empty_store_audit_is_valid_with_warning(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    report = (
        verify_autonomous_authorization_request_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 0
    assert report.verified_record_count == 0
    assert report.warnings


def test_missing_database_is_invalid(
    tmp_path,
) -> None:
    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            tmp_path / "missing.db"
        ).verify()
    )

    assert report.audit_valid is False
    assert report.errors


def test_missing_table_is_invalid(
    tmp_path,
) -> None:
    database = tmp_path / "empty.db"

    with sqlite3.connect(
        database
    ):
        pass

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.errors


def test_invalid_json_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET request_payload = ?
        WHERE sequence_number = 1
        """,
        (
            "{invalid-json",
        ),
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.record_hashes_valid is False


def test_non_object_payload_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET request_payload = ?
        WHERE sequence_number = 1
        """,
        (
            '["invalid"]',
        ),
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.payload_bindings_valid is False


def test_sequence_gap_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
        number=1,
    )

    append_request(
        store,
        tmp_path,
        number=2,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET sequence_number = 4
        WHERE sequence_number = 2
        """
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.sequence_continuous is False


def test_invalid_genesis_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET previous_record_hash = ?
        WHERE sequence_number = 1
        """,
        (
            "a" * 64,
        ),
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.genesis_valid is False
    assert report.hash_chain_valid is False


def test_broken_hash_chain_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
        number=1,
    )

    append_request(
        store,
        tmp_path,
        number=2,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET previous_record_hash = ?
        WHERE sequence_number = 2
        """,
        (
            "b" * 64,
        ),
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.hash_chain_valid is False


def test_record_hash_tampering_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET record_hash = ?
        WHERE sequence_number = 1
        """,
        (
            "c" * 64,
        ),
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.record_hashes_valid is False


def test_request_fingerprint_tampering_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    payload = load_payload(
        database
    )

    payload[
        "request_fingerprint"
    ] = "d" * 64

    update_payload(
        database,
        payload,
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.request_fingerprints_valid is False


@pytest.mark.parametrize(
    "field",
    [
        "authorization_request_id",
        "requester_id",
        "requested_at",
        "request_reason",
        "risk_class",
        "dry_run_required",
        "rollback_required",
        "verification_required",
    ],
)
def test_request_payload_binding_tampering_detected(
    tmp_path,
    field,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    payload = load_payload(
        database
    )

    payload[field] = (
        False
        if field.endswith(
            "_required"
        )
        else f"tampered:{field}"
    )

    update_payload(
        database,
        payload,
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.payload_bindings_valid is False


@pytest.mark.parametrize(
    "field",
    [
        "authorization_candidate_id",
        "candidate_record_hash",
        "candidate_fingerprint",
        "review_decision_id",
        "review_record_hash",
        "proposal_id",
        "proposal_record_hash",
        "candidate_audit_id",
    ],
)
def test_candidate_binding_tampering_detected(
    tmp_path,
    field,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    payload = load_payload(
        database
    )

    payload[field] = (
        f"tampered:{field}"
    )

    update_payload(
        database,
        payload,
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.candidate_bindings_valid is False


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "candidate_audit_valid",
            False,
        ),
        (
            "risk_class",
            "unknown",
        ),
        (
            "request_reason",
            "",
        ),
    ],
)
def test_request_policy_tampering_detected(
    tmp_path,
    field,
    value,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    payload = load_payload(
        database
    )

    payload[field] = value

    update_payload(
        database,
        payload,
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.request_policy_valid is False


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "authorization_request_created",
            False,
        ),
        (
            "authorization_created",
            True,
        ),
        (
            "authorization_approved",
            True,
        ),
        (
            "authorization_token_created",
            True,
        ),
        (
            "execution_lease_created",
            True,
        ),
        (
            "execution_allowed",
            True,
        ),
        (
            "can_execute",
            True,
        ),
    ],
)
def test_top_level_safety_tampering_detected(
    tmp_path,
    field,
    value,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    payload = load_payload(
        database
    )

    payload[field] = value

    update_payload(
        database,
        payload,
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.safety_contracts_valid is False


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "controlled_authorization_request_only",
            False,
        ),
        (
            "execution_authorization_created",
            True,
        ),
        (
            "authorization_approved",
            True,
        ),
        (
            "authorization_token_created",
            True,
        ),
        (
            "approval_claim_created",
            True,
        ),
        (
            "execution_lease_created",
            True,
        ),
        (
            "execution_allowed",
            True,
        ),
        (
            "execution_approved",
            True,
        ),
        (
            "simulation_started",
            True,
        ),
        (
            "network_io_performed",
            True,
        ),
        (
            "device_access_performed",
            True,
        ),
        (
            "command_generated",
            True,
        ),
        (
            "device_command_executed",
            True,
        ),
    ],
)
def test_nested_safety_tampering_detected(
    tmp_path,
    field,
    value,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    append_request(
        store,
        tmp_path,
    )

    payload = load_payload(
        database
    )

    payload["safety"][field] = value

    update_payload(
        database,
        payload,
    )

    report = (
        AutonomousAuthorizationRequestAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.safety_contracts_valid is False


def test_audit_report_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    report = (
        verify_autonomous_authorization_request_store(
            store
        )
    )

    payload = report.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "read_only_audit": True,
        "database_write_performed": False,
        "authorization_request_created": False,
        "authorization_request_modified": False,
        "execution_authorization_created": False,
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


def test_invalid_store_type_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "AutonomousAuthorizationRequestStore"
        ),
    ):
        verify_autonomous_authorization_request_store(
            "invalid"
        )
