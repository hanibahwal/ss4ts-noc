from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import sqlite3

import pytest

from app.models.autonomous_controlled_authorization_approval_candidate import (
    AutonomousControlledAuthorizationApprovalCandidate,
)
from app.services.autonomous_controlled_authorization_approval_candidate_store import (
    AutonomousApprovalCandidateDuplicate,
    AutonomousApprovalCandidateIntegrityError,
    AutonomousControlledAuthorizationApprovalCandidateStore,
)
from tests.test_autonomous_controlled_authorization_approval_candidate import (
    make_verified_sources,
)
from tests.test_autonomous_execution_authorization_binding_service import (
    NOW,
)


def make_candidate(
    tmp_path,
    *,
    suffix: str = "one",
):
    binding_record, binding_audit = (
        make_verified_sources(
            tmp_path
        )
    )

    candidate = (
        AutonomousControlledAuthorizationApprovalCandidate
        .from_verified_binding(
            approval_candidate_id=(
                f"approval-candidate:store:{suffix}"
            ),
            binding_record=binding_record,
            binding_audit=binding_audit,
            requested_by="operator:hani",
            approval_reason=(
                "Human approval required before "
                f"controlled execution {suffix}"
            ),
            requested_at=NOW,
            expires_at=(
                NOW
                + timedelta(
                    hours=2
                )
            ),
        )
    )

    if suffix == "one":
        return candidate

    def unique_hash(
        value: str,
    ) -> str:
        return hashlib.sha256(
            (
                value
                + ":"
                + suffix
            ).encode("utf-8")
        ).hexdigest()

    values = {
        "approval_candidate_id":
            candidate.approval_candidate_id,
        "binding_id":
            f"{candidate.binding_id}:{suffix}",
        "binding_record_hash":
            unique_hash(
                candidate.binding_record_hash
            ),
        "binding_fingerprint":
            unique_hash(
                candidate.binding_fingerprint
            ),
        "binding_audit_id":
            f"{candidate.binding_audit_id}:{suffix}",
        "binding_audit_valid":
            candidate.binding_audit_valid,
        "authorization_intent_id":
            (
                f"{candidate.authorization_intent_id}"
                f":{suffix}"
            ),
        "execution_authorization_id":
            (
                f"{candidate.execution_authorization_id}"
                f":{suffix}"
            ),
        "plan_id":
            f"{candidate.plan_id}:{suffix}",
        "decision_id":
            f"{candidate.decision_id}:{suffix}",
        "risk_class":
            candidate.risk_class,
        "authorization_status":
            candidate.authorization_status,
        "authorization_decision":
            candidate.authorization_decision,
        "requested_by":
            candidate.requested_by,
        "approval_reason":
            candidate.approval_reason,
        "requested_at":
            candidate.requested_at,
        "expires_at":
            candidate.expires_at,
    }

    provisional = (
        AutonomousControlledAuthorizationApprovalCandidate(
            **values,
            candidate_fingerprint="",
        )
    )

    return provisional


def test_append_candidate(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    record = store.append(
        candidate=make_candidate(
            tmp_path / "source"
        ),
        stored_at=NOW,
    )

    assert record.sequence_number == 1
    assert record.verify_hash() is True
    assert record.can_execute is False
    assert store.count() == 1
    assert store.verify_chain() is True


def test_candidate_lookup_methods(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    record = store.append(
        candidate=make_candidate(
            tmp_path / "source"
        ),
        stored_at=NOW,
    )

    assert store.get(1) == record

    assert (
        store.get_by_candidate_id(
            record.approval_candidate_id
        )
        == record
    )

    assert (
        store.get_by_binding_id(
            record.binding_id
        )
        == record
    )

    assert (
        store.get_by_execution_authorization_id(
            record.execution_authorization_id
        )
        == record
    )


def test_missing_records_return_none(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    assert store.get(999) is None
    assert store.get_by_candidate_id("missing") is None
    assert store.get_by_binding_id("missing") is None

    assert (
        store.get_by_execution_authorization_id(
            "missing"
        )
        is None
    )


def test_duplicate_candidate_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    candidate = make_candidate(
        tmp_path / "source"
    )

    store.append(
        candidate=candidate,
        stored_at=NOW,
    )

    with pytest.raises(
        AutonomousApprovalCandidateDuplicate,
    ):
        store.append(
            candidate=candidate,
            stored_at=NOW,
        )


def test_two_independent_candidates_form_chain(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    first = store.append(
        candidate=make_candidate(
            tmp_path / "first",
            suffix="first",
        ),
        stored_at=NOW,
    )

    second = store.append(
        candidate=make_candidate(
            tmp_path / "second",
            suffix="second",
        ),
        stored_at=NOW,
    )

    assert first.sequence_number == 1
    assert second.sequence_number == 2

    assert (
        second.previous_record_hash
        == first.record_hash
    )

    assert store.verify_chain() is True


def test_record_never_grants_execution(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    record = store.append(
        candidate=make_candidate(
            tmp_path / "source"
        ),
        stored_at=NOW,
    )

    payload = record.to_dict()

    assert record.approval_candidate_created is True
    assert record.authorization_approved is False
    assert record.approval_claim_created is False
    assert record.execution_allowed is False
    assert record.can_execute is False

    assert (
        payload["safety"]["immutable_record"]
        is True
    )
    assert (
        payload["safety"]["append_only"]
        is True
    )
    assert (
        payload["safety"]["approval_claim_created"]
        is False
    )


def test_expired_candidate_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    candidate = make_candidate(
        tmp_path / "source"
    )

    with pytest.raises(
        AutonomousApprovalCandidateIntegrityError,
        match="Expired",
    ):
        store.append(
            candidate=candidate,
            stored_at=(
                candidate.expires_at
                + timedelta(
                    seconds=1
                )
            ),
        )


def test_invalid_candidate_type_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    with pytest.raises(
        TypeError,
        match="candidate",
    ):
        store.append(
            candidate="invalid",
            stored_at=NOW,
        )


def test_naive_stored_at_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        store.append(
            candidate=make_candidate(
                tmp_path / "source"
            ),
            stored_at=datetime(
                2026,
                8,
                6,
                22,
                30,
            ),
        )


def test_tampered_record_hash_breaks_chain(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            database
        )
    )

    store.append(
        candidate=make_candidate(
            tmp_path / "source"
        ),
        stored_at=NOW,
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

    assert store.verify_chain() is False


def test_tampered_payload_breaks_chain(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            database
        )
    )

    store.append(
        candidate=make_candidate(
            tmp_path / "source"
        ),
        stored_at=NOW,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET candidate_payload = ?
            WHERE sequence_number = 1
            """,
            (
                '{"can_execute":true}',
            ),
        )
        connection.commit()

    assert store.verify_chain() is False


def test_list_records(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "candidates.db"
        )
    )

    first = store.append(
        candidate=make_candidate(
            tmp_path / "first",
            suffix="first",
        ),
        stored_at=NOW,
    )

    second = store.append(
        candidate=make_candidate(
            tmp_path / "second",
            suffix="second",
        ),
        stored_at=NOW,
    )

    records = store.list_records()

    assert records == [
        first,
        second,
    ]
