from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app.models.autonomous_controlled_authorization_human_decision import (
    AutonomousControlledAuthorizationHumanDecision,
    AutonomousControlledAuthorizationHumanDecisionType,
)
from app.services.autonomous_controlled_authorization_approval_candidate_audit import (
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


def make_verified_candidate(
    tmp_path,
):
    store = (
        AutonomousControlledAuthorizationApprovalCandidateStore(
            tmp_path / "approval-candidates.db"
        )
    )

    record = store.append(
        candidate=make_candidate(
            tmp_path / "source",
            suffix="human-decision",
        ),
        stored_at=NOW,
    )

    audit = (
        verify_autonomous_controlled_authorization_approval_candidate_store(
            store,
            audited_at=NOW,
        )
    )

    return record, audit


def make_decision(
    tmp_path,
    *,
    human_decision=(
        AutonomousControlledAuthorizationHumanDecisionType.APPROVED
    ),
):
    record, audit = make_verified_candidate(
        tmp_path
    )

    return (
        AutonomousControlledAuthorizationHumanDecision
        .from_verified_candidate(
            approval_decision_id=(
                "approval-decision:h25:1"
            ),
            candidate_record=record,
            candidate_audit=audit,
            reviewer_id="reviewer:hani",
            human_decision=human_decision,
            decision_reason=(
                "Human reviewer completed controlled "
                "authorization assessment"
            ),
            decided_at=(
                NOW
                + timedelta(
                    minutes=5
                )
            ),
        )
    )


@pytest.mark.parametrize(
    "decision_type",
    list(
        AutonomousControlledAuthorizationHumanDecisionType
    ),
)
def test_supported_decisions(
    tmp_path,
    decision_type,
) -> None:
    decision = make_decision(
        tmp_path,
        human_decision=decision_type,
    )

    assert (
        decision.human_decision
        is decision_type
    )

    assert (
        decision.decision_fingerprint
        == decision.calculate_fingerprint()
    )

    assert decision.human_decision_recorded is True
    assert decision.can_execute is False


def test_approved_decision_is_not_execution_approval(
    tmp_path,
) -> None:
    decision = make_decision(
        tmp_path
    )

    payload = decision.to_dict()

    assert decision.approved_by_human is True
    assert decision.authorization_approved is False
    assert (
        decision.authorization_token_created
        is False
    )
    assert decision.approval_claim_created is False
    assert decision.execution_lease_created is False
    assert decision.execution_allowed is False
    assert decision.can_execute is False

    assert (
        payload["safety"]["approved_by_human"]
        is True
    )

    assert (
        payload["safety"][
            "execution_authorization_approved"
        ]
        is False
    )


def test_rejected_decision_not_approved_by_human(
    tmp_path,
) -> None:
    decision = make_decision(
        tmp_path,
        human_decision="rejected",
    )

    assert decision.approved_by_human is False
    assert decision.can_execute is False


def test_decision_is_immutable(
    tmp_path,
) -> None:
    decision = make_decision(
        tmp_path
    )

    with pytest.raises(
        AttributeError,
    ):
        decision.reviewer_id = "changed"


def test_invalid_candidate_record_hash_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    tampered = replace(
        record,
        record_hash="f" * 64,
    )

    with pytest.raises(
        ValueError,
        match="record hash is invalid",
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                approval_decision_id="decision:tampered",
                candidate_record=tampered,
                candidate_audit=audit,
                reviewer_id="reviewer:hani",
                human_decision="approved",
                decision_reason="Reviewed",
                decided_at=NOW,
            )
        )


def test_invalid_candidate_audit_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    invalid_audit = replace(
        audit,
        record_hashes_valid=False,
    )

    with pytest.raises(
        ValueError,
        match="audit is invalid",
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                approval_decision_id="decision:bad-audit",
                candidate_record=record,
                candidate_audit=invalid_audit,
                reviewer_id="reviewer:hani",
                human_decision="approved",
                decision_reason="Reviewed",
                decided_at=NOW,
            )
        )


def test_expired_candidate_cannot_be_approved(
    tmp_path,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    expired_at = (
        datetime.fromisoformat(
            record.expires_at
        )
        + timedelta(
            seconds=1
        )
    )

    with pytest.raises(
        ValueError,
        match="Expired approval candidate",
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                approval_decision_id="decision:expired",
                candidate_record=record,
                candidate_audit=audit,
                reviewer_id="reviewer:hani",
                human_decision="approved",
                decision_reason="Reviewed too late",
                decided_at=expired_at,
            )
        )


def test_expired_candidate_can_be_marked_expired(
    tmp_path,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    expired_at = (
        datetime.fromisoformat(
            record.expires_at
        )
        + timedelta(
            seconds=1
        )
    )

    decision = (
        AutonomousControlledAuthorizationHumanDecision
        .from_verified_candidate(
            approval_decision_id="decision:expired-status",
            candidate_record=record,
            candidate_audit=audit,
            reviewer_id="reviewer:hani",
            human_decision="expired",
            decision_reason="Candidate validity elapsed",
            decided_at=expired_at,
        )
    )

    assert (
        decision.human_decision
        is
        AutonomousControlledAuthorizationHumanDecisionType.EXPIRED
    )
    assert decision.can_execute is False


@pytest.mark.parametrize(
    (
        "field_name",
        "field_value",
        "match",
    ),
    (
        (
            "reviewer_id",
            " ",
            "reviewer_id",
        ),
        (
            "decision_reason",
            " ",
            "decision_reason",
        ),
    ),
)
def test_required_text_rejected(
    tmp_path,
    field_name,
    field_value,
    match,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    values = {
        "approval_decision_id":
            "decision:required-text",
        "candidate_record":
            record,
        "candidate_audit":
            audit,
        "reviewer_id":
            "reviewer:hani",
        "human_decision":
            "approved",
        "decision_reason":
            "Reviewed",
        "decided_at":
            NOW,
    }

    values[
        field_name
    ] = field_value

    with pytest.raises(
        ValueError,
        match=match,
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                **values
            )
        )


def test_unsupported_decision_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="unsupported",
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                approval_decision_id="decision:unsupported",
                candidate_record=record,
                candidate_audit=audit,
                reviewer_id="reviewer:hani",
                human_decision="execute_now",
                decision_reason="Invalid decision",
                decided_at=NOW,
            )
        )


def test_naive_decided_at_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                approval_decision_id="decision:naive-time",
                candidate_record=record,
                candidate_audit=audit,
                reviewer_id="reviewer:hani",
                human_decision="approved",
                decision_reason="Reviewed",
                decided_at=datetime(
                    2026,
                    8,
                    6,
                    22,
                    30,
                ),
            )
        )


def test_fingerprint_mismatch_rejected(
    tmp_path,
) -> None:
    decision = make_decision(
        tmp_path
    )

    values = {
        field_name:
            getattr(
                decision,
                field_name,
            )
        for field_name in (
            "approval_decision_id",
            "approval_candidate_id",
            "candidate_record_hash",
            "candidate_fingerprint",
            "candidate_audit_id",
            "candidate_audit_valid",
            "binding_id",
            "execution_authorization_id",
            "plan_id",
            "source_decision_id",
            "risk_class",
            "reviewer_id",
            "human_decision",
            "decision_reason",
            "decided_at",
        )
    }

    with pytest.raises(
        ValueError,
        match="decision_fingerprint mismatch",
    ):
        AutonomousControlledAuthorizationHumanDecision(
            **values,
            decision_fingerprint="f" * 64,
        )


def test_invalid_source_types_rejected(
    tmp_path,
) -> None:
    record, audit = make_verified_candidate(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="candidate_record",
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                approval_decision_id="decision:invalid",
                candidate_record="invalid",
                candidate_audit=audit,
                reviewer_id="reviewer:hani",
                human_decision="approved",
                decision_reason="Reviewed",
                decided_at=NOW,
            )
        )

    with pytest.raises(
        TypeError,
        match="candidate_audit",
    ):
        (
            AutonomousControlledAuthorizationHumanDecision
            .from_verified_candidate(
                approval_decision_id="decision:invalid",
                candidate_record=record,
                candidate_audit="invalid",
                reviewer_id="reviewer:hani",
                human_decision="approved",
                decision_reason="Reviewed",
                decided_at=NOW,
            )
        )
