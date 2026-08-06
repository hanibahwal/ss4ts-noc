from __future__ import annotations

import json
import sqlite3

import pytest

from app.services.autonomous_authorization_candidate_audit import (
    AutonomousAuthorizationCandidateAuditVerifier,
    verify_autonomous_authorization_candidate_store,
)
from app.services.autonomous_authorization_candidate_store import (
    GENESIS_RECORD_HASH,
    AutonomousAuthorizationCandidateStore,
)
from tests.test_autonomous_authorization_candidate_store import (
    make_candidate,
)


TABLE = (
    "autonomous_authorization_candidate_records"
)


def append_candidate(
    store,
    tmp_path,
    *,
    number: int,
) -> None:
    store.append(
        candidate=make_candidate(
            tmp_path,
            number=number,
        )
    )


def update_database(
    database,
    statement: str,
    parameters: tuple = (),
) -> None:
    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            statement,
            parameters,
        )

        connection.commit()


def load_payload(
    database,
    *,
    sequence_number: int = 1,
) -> dict:
    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT candidate_payload
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
    payload: dict,
    *,
    sequence_number: int = 1,
) -> None:
    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET candidate_payload = ?
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


def test_valid_candidate_ledger_audit(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
    )

    append_candidate(
        store,
        tmp_path,
        number=2,
    )

    report = (
        verify_autonomous_authorization_candidate_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 2

    assert (
        report.verified_record_count
        == 2
    )

    assert (
        report.first_sequence_number
        == 1
    )

    assert (
        report.last_sequence_number
        == 2
    )

    assert report.errors == ()
    assert report.can_execute is False


def test_empty_ledger_is_valid_with_warning(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    report = (
        verify_autonomous_authorization_candidate_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 0

    assert (
        report.verified_record_count
        == 0
    )

    assert report.warnings


def test_missing_database_is_invalid(
    tmp_path,
) -> None:
    report = (
        AutonomousAuthorizationCandidateAuditVerifier(
            tmp_path / "missing.db"
        ).verify()
    )

    assert report.audit_valid is False

    assert any(
        "does not exist" in error
        for error in report.errors
    )


def test_missing_table_is_invalid(
    tmp_path,
) -> None:
    database = tmp_path / "empty.db"

    with sqlite3.connect(
        database
    ):
        pass

    report = (
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False

    assert any(
        "table does not exist" in error
        for error in report.errors
    )


def test_invalid_json_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET candidate_payload = ?
        WHERE sequence_number = 1
        """,
        (
            "{invalid-json",
        ),
    )

    report = (
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.record_hashes_valid is False


def test_non_object_payload_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET candidate_payload = ?
        WHERE sequence_number = 1
        """,
        (
            '["invalid"]',
        ),
    )

    report = (
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.payload_bindings_valid is False


def test_invalid_genesis_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
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
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.genesis_valid is False
    assert report.hash_chain_valid is False


def test_genesis_hash_constant_is_expected(
) -> None:
    assert (
        GENESIS_RECORD_HASH
        == "0" * 64
    )


def test_sequence_gap_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
    )

    append_candidate(
        store,
        tmp_path,
        number=2,
    )

    update_database(
        database,
        f"""
        UPDATE {TABLE}
        SET sequence_number = 3
        WHERE sequence_number = 2
        """
    )

    report = (
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.sequence_continuous is False


def test_broken_hash_chain_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
    )

    append_candidate(
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
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.hash_chain_valid is False


def test_record_hash_tampering_is_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
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
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False
    assert report.record_hashes_valid is False


def test_candidate_fingerprint_tampering_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
    )

    payload = load_payload(
        database
    )

    payload[
        "candidate_fingerprint"
    ] = "d" * 64

    update_payload(
        database,
        payload,
    )

    report = (
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False

    assert (
        report
        .candidate_fingerprints_valid
        is False
    )


@pytest.mark.parametrize(
    "field",
    [
        "authorization_candidate_id",
        "review_decision_id",
        "review_record_hash",
        "decision_fingerprint",
        "proposal_id",
        "proposal_record_hash",
        "queue_item_id",
        "reviewer_id",
        "review_audit_id",
    ],
)
def test_payload_binding_tampering_detected(
    tmp_path,
    field,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
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
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False

    assert (
        report.payload_bindings_valid
        is False
    )


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "review_audit_valid",
            False,
        ),
        (
            "eligible_for_authorization_review",
            False,
        ),
        (
            "human_decision",
            "rejected",
        ),
    ],
)
def test_candidate_eligibility_tampering_detected(
    tmp_path,
    field,
    value,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
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
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False

    assert (
        report.candidate_eligibility_valid
        is False
    )


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "authorization_created",
            True,
        ),
        (
            "approval_claim_created",
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
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
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
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False

    assert (
        report.safety_contracts_valid
        is False
    )


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "authorization_candidate_only",
            False,
        ),
        (
            "authorization_token_created",
            True,
        ),
        (
            "authorization_created",
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
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    append_candidate(
        store,
        tmp_path,
        number=1,
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
        AutonomousAuthorizationCandidateAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False

    assert (
        report.safety_contracts_valid
        is False
    )


def test_audit_report_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    report = (
        verify_autonomous_authorization_candidate_store(
            store
        )
    )

    payload = report.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "read_only_audit": True,
        "database_write_performed": False,
        "candidate_created": False,
        "candidate_modified": False,
        "authorization_created": False,
        "authorization_token_created": False,
        "approval_claim_created": False,
        "execution_lease_created": False,
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
            "AutonomousAuthorizationCandidateStore"
        ),
    ):
        verify_autonomous_authorization_candidate_store(
            "invalid"
        )
