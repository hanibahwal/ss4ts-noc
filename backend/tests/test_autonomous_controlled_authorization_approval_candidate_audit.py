from __future__ import annotations

from datetime import datetime
import json
import sqlite3

import pytest

from app.services.autonomous_controlled_authorization_approval_candidate_audit import (
    AutonomousApprovalCandidateAuditReport,
    AutonomousApprovalCandidateAuditVerifier,
    verify_autonomous_controlled_authorization_approval_candidate_store,
)
from app.services.autonomous_controlled_authorization_approval_candidate_store import (
    AutonomousControlledAuthorizationApprovalCandidateStore,
)
from tests.test_autonomous_controlled_authorization_approval_candidate_store import (
    make_candidate,
)
from tests.test_autonomous_execution_authorization_binding_service import (
    NOW,
)


def make_store(
    tmp_path,
    *,
    count: int = 1,
):
    database = (
        tmp_path
        / "approval-candidates.db"
    )

    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            database
        )
    )

    for index in range(
        count
    ):
        suffix = (
            "one"
            if index == 0
            else f"candidate-{index + 1}"
        )

        store.append(
            candidate=make_candidate(
                tmp_path
                / f"source-{index}",
                suffix=suffix,
            ),
            stored_at=NOW,
        )

    return store, database


def test_valid_store_audit(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path,
        count=2,
    )

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert isinstance(
        report,
        AutonomousApprovalCandidateAuditReport,
    )

    assert report.record_count == 2
    assert report.first_sequence_number == 1
    assert report.last_sequence_number == 2

    assert report.record_hashes_valid is True
    assert report.hash_chain_valid is True
    assert report.sequence_integrity_valid is True
    assert report.candidate_fingerprints_valid is True
    assert report.candidate_payloads_valid is True
    assert report.binding_audits_valid is True
    assert report.expiry_consistency_valid is True
    assert report.authorization_states_valid is True
    assert report.duplicate_identities_valid is True
    assert report.safety_claims_valid is True

    assert report.issues == ()
    assert report.audit_valid is True
    assert report.can_execute is False


def test_empty_store_is_valid(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path,
        count=0,
    )

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.record_count == 0
    assert report.first_sequence_number is None
    assert report.last_sequence_number is None
    assert report.audit_valid is True


def test_audit_report_is_never_executable(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path
    )

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    payload = report.to_dict()

    assert report.authorization_approved is False
    assert report.approval_claim_created is False
    assert report.execution_lease_created is False
    assert report.execution_allowed is False
    assert report.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["read_only_audit"]
        is True
    )

    assert (
        payload["safety"]["store_mutated"]
        is False
    )


def test_audit_does_not_modify_store(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path,
        count=2,
    )

    before_count = store.count()

    with sqlite3.connect(
        database
    ) as connection:
        before_changes = (
            connection.total_changes
        )

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    with sqlite3.connect(
        database
    ) as connection:
        after_changes = (
            connection.total_changes
        )

    assert report.audit_valid is True
    assert store.count() == before_count
    assert before_changes == after_changes


def test_tampered_record_hash_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET record_hash = ?
            WHERE sequence_number = 1
            """,
            (
                "f" * 64,
            ),
        )
        connection.commit()

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.record_hashes_valid is False
    assert report.audit_valid is False
    assert report.issues


def test_broken_previous_hash_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path,
        count=2,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET previous_record_hash = ?
            WHERE sequence_number = 2
            """,
            (
                "a" * 64,
            ),
        )
        connection.commit()

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.hash_chain_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_payload_binding_mismatch_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT candidate_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["requested_by"] = (
            "tampered-operator"
        )

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET candidate_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.candidate_payloads_valid is False
    assert report.candidate_fingerprints_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_unsafe_claim_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT candidate_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["can_execute"] = True

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET candidate_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.safety_claims_valid is False
    assert report.audit_valid is False


def test_invalid_binding_audit_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET binding_audit_valid = 0
            WHERE sequence_number = 1
            """
        )
        connection.commit()

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.binding_audits_valid is False
    assert report.candidate_payloads_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_invalid_authorization_state_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET authorization_status = ?
            WHERE sequence_number = 1
            """,
            (
                "approved",
            ),
        )
        connection.commit()

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.authorization_states_valid is False
    assert report.audit_valid is False


def test_invalid_expiry_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET expires_at = requested_at
            WHERE sequence_number = 1
            """
        )
        connection.commit()

    report = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    assert report.expiry_consistency_valid is False
    assert report.audit_valid is False


def test_invalid_inputs_rejected(
    tmp_path,
) -> None:
    verifier = (
        AutonomousApprovalCandidateAuditVerifier()
    )

    with pytest.raises(
        TypeError,
        match="store",
    ):
        verifier.verify(
            store="invalid",
            audited_at=NOW,
        )

    store, _ = make_store(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        verifier.verify(
            store=store,
            audited_at=datetime(
                2026,
                8,
                6,
                22,
                30,
            ),
        )
