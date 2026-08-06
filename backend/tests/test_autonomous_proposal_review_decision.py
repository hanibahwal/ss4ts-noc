from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.autonomous_operation_proposal import (
    AutonomousOperationMode,
    AutonomousOperationProposal,
    AutonomousPolicyStatus,
    AutonomousProposalRiskLevel,
)
from app.models.autonomous_proposal_review_decision import (
    AutonomousHumanReviewDecisionType,
    AutonomousProposalHumanReviewDecision,
)
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBindingResult,
)
from app.services.autonomous_proposal_policy import (
    AutonomousProposalPolicyResult,
)
from app.services.autonomous_proposal_review_decision import (
    AutonomousProposalHumanReviewService,
    create_autonomous_proposal_human_review,
)
from app.services.autonomous_proposal_review_queue import (
    build_autonomous_proposal_review_queue,
)
from app.services.autonomous_proposal_store import (
    AutonomousProposalStore,
)


NOW = datetime(
    2026,
    8,
    6,
    14,
    30,
    tzinfo=timezone.utc,
)


def make_queue_item(
    tmp_path,
):
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    proposal_id = (
        "proposal:human-review"
    )

    proposal = AutonomousOperationProposal(
        proposal_id=proposal_id,
        source_signal_id=(
            "signal:human-review"
        ),
        decision_id=(
            "decision:human-review"
        ),
        plan_id=(
            "plan:human-review"
        ),
        target_node_id=(
            "device:router-01"
        ),
        operation_type=(
            "disable_interface"
        ),
        summary=(
            "Review interface action"
        ),
        reason=(
            "Interface instability"
        ),
        confidence_percent=93,
        risk_level=(
            AutonomousProposalRiskLevel.HIGH
        ),
        policy_status=(
            AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
        ),
        operating_mode=(
            AutonomousOperationMode
            .APPROVAL_CANDIDATE
        ),
        requires_human_approval=True,
        created_at=(
            NOW
            - timedelta(hours=1)
        ),
        expires_at=(
            NOW
            + timedelta(hours=1)
        ),
    )

    policy = AutonomousProposalPolicyResult(
        proposal_id=proposal_id,
        policy_status=(
            AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
        ),
        operating_mode=(
            AutonomousOperationMode
            .APPROVAL_CANDIDATE
        ),
        requires_human_approval=True,
        allowed_for_review=True,
        blocked=False,
        reasons=(
            "Human approval required",
        ),
        confidence_threshold=70,
        evaluated_confidence=93,
    )

    binding = AutonomousProposalBindingResult(
        proposal_id=proposal_id,
        decision_id=(
            "decision:human-review"
        ),
        plan_id=(
            "plan:human-review"
        ),
        binding_valid=True,
        binding_errors=(),
        decision_consistent=True,
        plan_consistent=True,
        target_consistent=True,
        operation_consistent=True,
        confidence_consistent=True,
        risk_consistent=True,
        policy_review_allowed=True,
        proposal_not_expired=True,
        human_approval_required=True,
        dry_run_only=True,
    )

    store.append(
        proposal=proposal,
        policy=policy,
        binding=binding,
    )

    queue = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert queue.audit_valid is True
    assert len(queue.items) == 1

    return queue, queue.items[0]


@pytest.mark.parametrize(
    "decision",
    [
        AutonomousHumanReviewDecisionType
        .APPROVED_FOR_AUTHORIZATION_REVIEW,
        AutonomousHumanReviewDecisionType
        .REJECTED,
        AutonomousHumanReviewDecisionType
        .CHANGES_REQUESTED,
    ],
)
def test_all_human_review_decisions_supported(
    tmp_path,
    decision,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    result = (
        create_autonomous_proposal_human_review(
            queue_item=item,
            reviewer_id="reviewer:hani",
            reviewer_name="Hani Bahwal",
            decision=decision,
            reason="Reviewed manually",
            audit_id=queue.audit_id,
            audit_valid=queue.audit_valid,
            reviewed_at=NOW,
            review_decision_id=(
                f"human-review:{decision.value}"
            ),
        )
    )

    assert isinstance(
        result,
        AutonomousProposalHumanReviewDecision,
    )

    assert result.decision is decision
    assert result.can_execute is False
    assert result.authorization_created is False


def test_approval_only_requests_authorization_review(
    tmp_path,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    result = (
        create_autonomous_proposal_human_review(
            queue_item=item,
            reviewer_id="reviewer:hani",
            reviewer_name="Hani Bahwal",
            decision=(
                "approved_for_authorization_review"
            ),
            reason=(
                "Proposal may proceed to a "
                "separate authorization review"
            ),
            audit_id=queue.audit_id,
            audit_valid=True,
            reviewed_at=NOW,
        )
    )

    assert (
        result
        .approved_for_authorization_review
        is True
    )

    assert (
        result
        .requires_controlled_authorization
        is True
    )

    assert result.authorization_created is False
    assert result.can_execute is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewer_id", ""),
        ("reviewer_name", "   "),
        ("reason", ""),
        ("audit_id", " "),
    ],
)
def test_required_fields_rejected(
    tmp_path,
    field,
    value,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    arguments = {
        "queue_item": item,
        "reviewer_id": (
            "reviewer:hani"
        ),
        "reviewer_name": (
            "Hani Bahwal"
        ),
        "decision": (
            AutonomousHumanReviewDecisionType
            .REJECTED
        ),
        "reason": (
            "Unsafe proposal"
        ),
        "audit_id": queue.audit_id,
        "audit_valid": True,
        "reviewed_at": NOW,
    }

    arguments[field] = value

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        create_autonomous_proposal_human_review(
            **arguments
        )


def test_invalid_decision_rejected(
    tmp_path,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="Unsupported",
    ):
        create_autonomous_proposal_human_review(
            queue_item=item,
            reviewer_id="reviewer:hani",
            reviewer_name="Hani Bahwal",
            decision="execute_now",
            reason="Invalid decision",
            audit_id=queue.audit_id,
            audit_valid=True,
            reviewed_at=NOW,
        )


def test_failed_audit_rejected(
    tmp_path,
) -> None:
    _, item = make_queue_item(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="valid proposal audit",
    ):
        create_autonomous_proposal_human_review(
            queue_item=item,
            reviewer_id="reviewer:hani",
            reviewer_name="Hani Bahwal",
            decision=(
                AutonomousHumanReviewDecisionType
                .REJECTED
            ),
            reason="Audit failed",
            audit_id="audit:failed",
            audit_valid=False,
            reviewed_at=NOW,
        )


def test_invalid_queue_item_type_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "AutonomousProposalReviewQueueItem"
        ),
    ):
        (
            AutonomousProposalHumanReviewService
            .create_decision(
                queue_item="invalid",
                reviewer_id="reviewer:hani",
                reviewer_name="Hani Bahwal",
                decision=(
                    AutonomousHumanReviewDecisionType
                    .REJECTED
                ),
                reason="Invalid item",
                audit_id="audit:1",
                audit_valid=True,
                reviewed_at=NOW,
            )
        )


def test_snapshot_is_bound_to_queue_item(
    tmp_path,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    result = (
        create_autonomous_proposal_human_review(
            queue_item=item,
            reviewer_id="reviewer:hani",
            reviewer_name="Hani Bahwal",
            decision=(
                AutonomousHumanReviewDecisionType
                .CHANGES_REQUESTED
            ),
            reason=(
                "More operational evidence "
                "is required"
            ),
            audit_id=queue.audit_id,
            audit_valid=True,
            reviewed_at=NOW,
        )
    )

    assert (
        result.proposal_snapshot
        == item.to_dict()
    )

    assert (
        result.record_hash
        == item.record_hash
    )

    assert (
        result.queue_priority_score
        == item.priority_score
    )


def test_fingerprint_is_deterministic(
    tmp_path,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    arguments = {
        "queue_item": item,
        "reviewer_id": (
            "reviewer:hani"
        ),
        "reviewer_name": (
            "Hani Bahwal"
        ),
        "decision": (
            AutonomousHumanReviewDecisionType
            .REJECTED
        ),
        "reason": (
            "Risk is unacceptable"
        ),
        "audit_id": queue.audit_id,
        "audit_valid": True,
        "reviewed_at": NOW,
        "review_decision_id": (
            "human-review:fixed"
        ),
    }

    first = (
        create_autonomous_proposal_human_review(
            **arguments
        )
    )

    second = (
        create_autonomous_proposal_human_review(
            **arguments
        )
    )

    assert (
        first.decision_fingerprint
        == second.decision_fingerprint
    )

    assert (
        len(
            first.decision_fingerprint
        )
        == 64
    )


def test_tampered_fingerprint_rejected(
    tmp_path,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    valid = (
        create_autonomous_proposal_human_review(
            queue_item=item,
            reviewer_id="reviewer:hani",
            reviewer_name="Hani Bahwal",
            decision=(
                AutonomousHumanReviewDecisionType
                .REJECTED
            ),
            reason="Rejected manually",
            audit_id=queue.audit_id,
            audit_valid=True,
            reviewed_at=NOW,
            review_decision_id=(
                "human-review:tamper"
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="fingerprint mismatch",
    ):
        AutonomousProposalHumanReviewDecision(
            review_decision_id=(
                valid.review_decision_id
            ),
            queue_item_id=(
                valid.queue_item_id
            ),
            proposal_id=(
                valid.proposal_id
            ),
            record_hash=(
                valid.record_hash
            ),
            reviewer_id=(
                valid.reviewer_id
            ),
            reviewer_name=(
                valid.reviewer_name
            ),
            decision=valid.decision,
            reason="Tampered reason",
            reviewed_at=(
                valid.reviewed_at
            ),
            proposal_snapshot=(
                valid.proposal_snapshot
            ),
            queue_priority_score=(
                valid.queue_priority_score
            ),
            audit_id=valid.audit_id,
            audit_valid=True,
            decision_fingerprint=(
                valid.decision_fingerprint
            ),
        )


def test_safety_metadata_forbids_execution(
    tmp_path,
) -> None:
    queue, item = make_queue_item(
        tmp_path
    )

    result = (
        create_autonomous_proposal_human_review(
            queue_item=item,
            reviewer_id="reviewer:hani",
            reviewer_name="Hani Bahwal",
            decision=(
                AutonomousHumanReviewDecisionType
                .APPROVED_FOR_AUTHORIZATION_REVIEW
            ),
            reason="Human review completed",
            audit_id=queue.audit_id,
            audit_valid=True,
            reviewed_at=NOW,
        )
    )

    payload = result.to_dict()

    assert payload["can_execute"] is False

    assert (
        payload["authorization_created"]
        is False
    )

    assert payload["safety"] == {
        "human_originated_decision": True,
        "automatic_approval": False,
        "immutable_proposal_modified": False,
        "approval_claim_created": False,
        "authorization_created": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
    }
