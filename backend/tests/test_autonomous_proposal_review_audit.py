from __future__ import annotations

import sqlite3

import pytest

from app.services.autonomous_proposal_review_audit import (
    AutonomousProposalReviewAuditVerifier,
    verify_autonomous_proposal_review_store,
)
from app.services.autonomous_proposal_review_store import (
    AutonomousProposalReviewStore,
)
from tests.test_autonomous_proposal_review_store import (
    make_decision,
)


def append_decision(
    store: AutonomousProposalReviewStore,
    tmp_path,
    *,
    number: int,
) -> None:
    decision = make_decision(
        tmp_path,
        proposal_id=(
            f"proposal:audit-{number}"
        ),
        review_decision_id=(
            f"human-review:audit-{number}"
        ),
    )

    store.append(
        decision=decision
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


def test_valid_review_ledger_passes_audit(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    append_decision(
        store,
        tmp_path,
        number=2,
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 2
    assert report.verified_record_count == 2

    assert (
        report.first_sequence_number
        == 1
    )

    assert (
        report.last_sequence_number
        == 2
    )

    assert report.errors == ()


def test_empty_review_ledger_is_valid_with_warning(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is True
    assert report.record_count == 0

    assert report.warnings == (
        "Autonomous review decision "
        "ledger is empty",
    )


def test_missing_database_is_reported(
    tmp_path,
) -> None:
    report = (
        AutonomousProposalReviewAuditVerifier(
            tmp_path / "missing.db"
        ).verify()
    )

    assert report.audit_valid is False
    assert report.record_count == 0

    assert (
        "does not exist"
        in report.errors[0]
    )


def test_missing_table_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "invalid.db"
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            "CREATE TABLE unrelated "
            "(id INTEGER)"
        )

        connection.commit()

    report = (
        AutonomousProposalReviewAuditVerifier(
            database
        ).verify()
    )

    assert report.audit_valid is False

    assert (
        "Unable to read"
        in report.errors[0]
    )


def test_tampered_payload_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        """
        UPDATE
            autonomous_proposal_review_records
        SET decision_payload = ?
        WHERE sequence_number = 1
        """,
        (
            '{"tampered":true}',
        ),
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False
    assert report.record_hashes_valid is False
    assert report.payload_bindings_valid is False
    assert report.decision_fingerprints_valid is False


def test_invalid_json_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        """
        UPDATE
            autonomous_proposal_review_records
        SET decision_payload = ?
        WHERE sequence_number = 1
        """,
        (
            "{invalid-json",
        ),
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False

    assert any(
        "invalid JSON"
        in error
        for error in report.errors
    )


def test_sequence_gap_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    append_decision(
        store,
        tmp_path,
        number=2,
    )

    update_database(
        database,
        """
        UPDATE
            autonomous_proposal_review_records
        SET sequence_number = 4
        WHERE sequence_number = 2
        """,
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False

    assert (
        report.sequence_continuous
        is False
    )


def test_invalid_genesis_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        """
        UPDATE
            autonomous_proposal_review_records
        SET previous_record_hash = ?
        WHERE sequence_number = 1
        """,
        (
            "f" * 64,
        ),
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False
    assert report.genesis_valid is False
    assert report.hash_chain_valid is False


def test_broken_hash_chain_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    append_decision(
        store,
        tmp_path,
        number=2,
    )

    update_database(
        database,
        """
        UPDATE
            autonomous_proposal_review_records
        SET previous_record_hash = ?
        WHERE sequence_number = 2
        """,
        (
            "a" * 64,
        ),
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False
    assert report.hash_chain_valid is False


@pytest.mark.parametrize(
    "column,payload_field,new_value",
    [
        (
            "review_decision_id",
            "review_decision_id",
            "human-review:tampered",
        ),
        (
            "queue_item_id",
            "queue_item_id",
            "review:tampered",
        ),
        (
            "proposal_id",
            "proposal_id",
            "proposal:tampered",
        ),
        (
            "proposal_record_hash",
            "record_hash",
            "b" * 64,
        ),
        (
            "reviewer_id",
            "reviewer_id",
            "reviewer:tampered",
        ),
        (
            "decision",
            "decision",
            "rejected",
        ),
    ],
)
def test_payload_column_binding_mismatch_is_reported(
    tmp_path,
    column,
    payload_field,
    new_value,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        f"""
        UPDATE
            autonomous_proposal_review_records
        SET {column} = ?
        WHERE sequence_number = 1
        """,
        (
            new_value,
        ),
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False
    assert report.payload_bindings_valid is False

    assert any(
        payload_field
        in error
        for error in report.errors
    )


def test_unsupported_decision_type_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        """
        UPDATE
            autonomous_proposal_review_records
        SET decision = ?
        WHERE sequence_number = 1
        """,
        (
            "execute_immediately",
        ),
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False
    assert report.decision_types_valid is False


def test_decision_fingerprint_tampering_is_reported(
    tmp_path,
) -> None:
    database = (
        tmp_path / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    update_database(
        database,
        """
        UPDATE
            autonomous_proposal_review_records
        SET decision_fingerprint = ?
        WHERE sequence_number = 1
        """,
        (
            "c" * 64,
        ),
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    assert report.audit_valid is False

    assert (
        report.decision_fingerprints_valid
        is False
    )


def test_audit_does_not_modify_store(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    append_decision(
        store,
        tmp_path,
        number=1,
    )

    before = store.count()

    verify_autonomous_proposal_review_store(
        store
    )

    after = store.count()

    assert before == after == 1


def test_audit_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    report = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    payload = report.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "read_only_audit": True,
        "database_write_performed": False,
        "review_decision_created": False,
        "review_decision_modified": False,
        "proposal_ledger_modified": False,
        "approval_claim_created": False,
        "authorization_created": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
    }


def test_invalid_store_type_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "AutonomousProposalReviewStore"
        ),
    ):
        verify_autonomous_proposal_review_store(
            "invalid"
        )
