from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.models.autonomous_authorization_candidate import (
    AutonomousAuthorizationReviewCandidate,
)
from app.models.autonomous_proposal_review_decision import (
    AutonomousHumanReviewDecisionType,
)
from app.services.autonomous_authorization_candidate import (
    create_autonomous_authorization_candidate,
)
from app.services.autonomous_proposal_review_audit import (
    verify_autonomous_proposal_review_store,
)
from app.services.autonomous_proposal_review_store import (
    AutonomousProposalReviewStore,
)
from tests.test_autonomous_proposal_review_store import (
    make_decision,
)


NOW = datetime(
    2026,
    8,
    6,
    19,
    55,
    tzinfo=timezone.utc,
)


def make_context(
    tmp_path,
    *,
    decision_type: (
        AutonomousHumanReviewDecisionType
    ) = (
        AutonomousHumanReviewDecisionType
        .APPROVED_FOR_AUTHORIZATION_REVIEW
    ),
):
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    decision = make_decision(
        tmp_path,
        proposal_id=(
            "proposal:authorization-candidate"
        ),
        review_decision_id=(
            "human-review:"
            "authorization-candidate"
        ),
        decision_type=decision_type,
    )

    record = store.append(
        decision=decision
    )

    audit = (
        verify_autonomous_proposal_review_store(
            store
        )
    )

    return store, record, audit


def test_create_authorization_candidate(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    candidate = (
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=audit,
            created_at=NOW,
            authorization_candidate_id=(
                "authorization-candidate:test"
            ),
        )
    )

    assert isinstance(
        candidate,
        AutonomousAuthorizationReviewCandidate,
    )

    assert (
        candidate.review_decision_id
        == record.review_decision_id
    )

    assert (
        candidate.review_record_hash
        == record.record_hash
    )

    assert (
        candidate.decision_fingerprint
        == record.decision_fingerprint
    )

    assert (
        candidate.proposal_record_hash
        == record.proposal_record_hash
    )


def test_candidate_is_not_authorization(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    candidate = (
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=audit,
            created_at=NOW,
        )
    )

    assert (
        candidate
        .eligible_for_authorization_review
        is True
    )

    assert (
        candidate.authorization_created
        is False
    )

    assert (
        candidate.approval_claim_created
        is False
    )

    assert candidate.can_execute is False


@pytest.mark.parametrize(
    "decision_type",
    [
        (
            AutonomousHumanReviewDecisionType
            .REJECTED
        ),
        (
            AutonomousHumanReviewDecisionType
            .CHANGES_REQUESTED
        ),
    ],
)
def test_non_approved_decisions_are_rejected(
    tmp_path,
    decision_type,
) -> None:
    _, record, audit = make_context(
        tmp_path,
        decision_type=decision_type,
    )

    with pytest.raises(
        ValueError,
        match=(
            "approved for authorization review"
        ),
    ):
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=audit,
        )


def test_invalid_review_audit_is_rejected(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    invalid_audit = replace(
        audit,
        record_hashes_valid=False,
        errors=(
            "Review record hash mismatch",
        ),
    )

    assert invalid_audit.audit_valid is False

    with pytest.raises(
        ValueError,
        match="valid human review store audit",
    ):
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=invalid_audit,
        )


def test_tampered_record_hash_is_rejected(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    tampered = replace(
        record,
        record_hash=(
            "f" * 64
        ),
    )

    with pytest.raises(
        ValueError,
        match="record hash",
    ):
        create_autonomous_authorization_candidate(
            review_record=tampered,
            review_audit=audit,
        )


@pytest.mark.parametrize(
    "field,new_value",
    [
        (
            "review_decision_id",
            "human-review:tampered",
        ),
        (
            "decision_fingerprint",
            "a" * 64,
        ),
        (
            "queue_item_id",
            "review:tampered",
        ),
        (
            "proposal_id",
            "proposal:tampered",
        ),
        (
            "proposal_record_hash",
            "b" * 64,
        ),
        (
            "reviewer_id",
            "reviewer:tampered",
        ),
    ],
)
def test_payload_binding_mismatch_is_rejected(
    tmp_path,
    field,
    new_value,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    tampered = replace(
        record,
        **{
            field: new_value,
        },
    )

    with pytest.raises(
        ValueError,
    ):
        create_autonomous_authorization_candidate(
            review_record=tampered,
            review_audit=audit,
        )


def test_candidate_fingerprint_is_deterministic(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    first = (
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=audit,
            created_at=NOW,
            authorization_candidate_id=(
                "authorization-candidate:"
                "deterministic"
            ),
        )
    )

    second = (
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=audit,
            created_at=NOW,
            authorization_candidate_id=(
                "authorization-candidate:"
                "deterministic"
            ),
        )
    )

    assert (
        first.candidate_fingerprint
        == second.candidate_fingerprint
    )

    assert (
        first.calculate_fingerprint()
        == first.candidate_fingerprint
    )


def test_candidate_fingerprint_mismatch_rejected(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    valid = (
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=audit,
            created_at=NOW,
            authorization_candidate_id=(
                "authorization-candidate:valid"
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="fingerprint mismatch",
    ):
        AutonomousAuthorizationReviewCandidate(
            authorization_candidate_id=(
                valid.authorization_candidate_id
            ),
            review_decision_id=(
                valid.review_decision_id
            ),
            review_record_hash=(
                valid.review_record_hash
            ),
            decision_fingerprint=(
                valid.decision_fingerprint
            ),
            proposal_id=(
                valid.proposal_id
            ),
            proposal_record_hash=(
                valid.proposal_record_hash
            ),
            queue_item_id=(
                valid.queue_item_id
            ),
            reviewer_id=(
                valid.reviewer_id
            ),
            human_decision=(
                valid.human_decision
            ),
            review_audit_id=(
                valid.review_audit_id
            ),
            review_audit_valid=True,
            created_at=valid.created_at,
            candidate_fingerprint=(
                "0" * 64
            ),
        )


def test_candidate_safety_metadata(
    tmp_path,
) -> None:
    _, record, audit = make_context(
        tmp_path
    )

    candidate = (
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit=audit,
            created_at=NOW,
        )
    )

    payload = candidate.to_dict()

    assert payload["can_execute"] is False
    assert (
        payload["authorization_created"]
        is False
    )

    assert payload["safety"] == {
        "authorization_candidate_only": True,
        "authorization_token_created": False,
        "authorization_created": False,
        "approval_claim_created": False,
        "execution_lease_created": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_access_performed": False,
        "command_generated": False,
        "device_command_executed": False,
    }


def test_invalid_record_type_rejected(
    tmp_path,
) -> None:
    _, _, audit = make_context(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="AutonomousProposalReviewRecord",
    ):
        create_autonomous_authorization_candidate(
            review_record="invalid",
            review_audit=audit,
        )


def test_invalid_audit_type_rejected(
    tmp_path,
) -> None:
    _, record, _ = make_context(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match=(
            "AutonomousProposalReviewAuditReport"
        ),
    ):
        create_autonomous_authorization_candidate(
            review_record=record,
            review_audit="invalid",
        )
