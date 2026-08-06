from __future__ import annotations

from datetime import datetime
import json
import sqlite3

import pytest

from app.services.autonomous_controlled_authorization_human_decision_audit import (
    AutonomousHumanApprovalDecisionAuditReport,
    AutonomousHumanApprovalDecisionAuditVerifier,
    verify_autonomous_controlled_authorization_human_decision_store,
)
from app.services.autonomous_controlled_authorization_human_decision_store import (
    AutonomousControlledAuthorizationHumanDecisionStore,
)
from tests.test_autonomous_controlled_authorization_human_decision_store import (
    append_decision,
    make_decision,
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
        / "human-decisions.db"
    )

    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            database
        )
    )

    for index in range(
        count
    ):
        suffix = (
            "one"
            if index == 0
            else f"decision-{index + 1}"
        )

        decision_type = (
            "approved"
            if index == 0
            else "rejected"
        )

        append_decision(
            store,
            make_decision(
                tmp_path,
                suffix=suffix,
                human_decision=decision_type,
            ),
        )

    return store, database


def audit_store(
    store,
):
    return (
        verify_autonomous_controlled_authorization_human_decision_store(
            store,
            audited_at=NOW,
        )
    )


def test_valid_human_decision_store_audit(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path,
        count=2,
    )

    report = audit_store(
        store
    )

    assert isinstance(
        report,
        AutonomousHumanApprovalDecisionAuditReport,
    )

    assert report.record_count == 2
    assert report.first_sequence_number == 1
    assert report.last_sequence_number == 2

    assert report.record_hashes_valid is True
    assert report.hash_chain_valid is True
    assert report.sequence_integrity_valid is True
    assert report.decision_fingerprints_valid is True
    assert report.decision_payloads_valid is True
    assert report.candidate_audits_valid is True
    assert report.human_decisions_valid is True
    assert report.timestamp_consistency_valid is True
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

    report = audit_store(
        store
    )

    assert report.record_count == 0
    assert report.first_sequence_number is None
    assert report.last_sequence_number is None
    assert report.audit_valid is True


def test_report_never_allows_execution(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path
    )

    report = audit_store(
        store
    )

    payload = report.to_dict()

    assert report.authorization_approved is False
    assert (
        report.authorization_token_created
        is False
    )
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
    store, _ = make_store(
        tmp_path,
        count=2,
    )

    before_count = store.count()

    report = audit_store(
        store
    )

    assert report.audit_valid is True
    assert store.count() == before_count


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

    report = audit_store(
        store
    )

    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_broken_hash_chain_detected(
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

    report = audit_store(
        store
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
            SELECT decision_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["reviewer_id"] = (
            "reviewer:tampered"
        )

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET decision_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.decision_payloads_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_decision_fingerprint_mismatch_detected(
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
            SET decision_reason = ?
            WHERE sequence_number = 1
            """,
            (
                "Tampered reason",
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert (
        report.decision_fingerprints_valid
        is False
    )
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_invalid_candidate_audit_detected(
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
            SET candidate_audit_valid = 0
            WHERE sequence_number = 1
            """
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.candidate_audits_valid is False
    assert report.decision_payloads_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_unsupported_human_decision_detected(
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
            SET human_decision = ?
            WHERE sequence_number = 1
            """,
            (
                "execute_now",
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.human_decisions_valid is False
    assert report.audit_valid is False


def test_invalid_timestamp_order_detected(
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
            SET stored_at = ?
            WHERE sequence_number = 1
            """,
            (
                "2020-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert (
        report.timestamp_consistency_valid
        is False
    )
    assert report.audit_valid is False


def test_unsafe_execution_claim_detected(
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
            SELECT decision_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["approval_claim_created"] = True
        payload["can_execute"] = True

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET decision_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.safety_claims_valid is False
    assert report.audit_valid is False


def test_invalid_inputs_rejected(
    tmp_path,
) -> None:
    verifier = (
        AutonomousHumanApprovalDecisionAuditVerifier()
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
                40,
            ),
        )
