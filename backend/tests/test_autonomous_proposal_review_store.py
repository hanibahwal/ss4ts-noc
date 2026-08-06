from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import sqlite3

import pytest

from app.models.autonomous_operation_proposal import (
    AutonomousOperationMode,
    AutonomousOperationProposal,
    AutonomousPolicyStatus,
    AutonomousProposalRiskLevel,
)
from app.models.autonomous_proposal_review_decision import (
    AutonomousHumanReviewDecisionType,
)
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBindingResult,
)
from app.services.autonomous_proposal_policy import (
    AutonomousProposalPolicyResult,
)
from app.services.autonomous_proposal_review_decision import (
    create_autonomous_proposal_human_review,
)
from app.services.autonomous_proposal_review_queue import (
    build_autonomous_proposal_review_queue,
)
from app.services.autonomous_proposal_review_store import (
    GENESIS_RECORD_HASH,
    AutonomousProposalReviewDuplicate,
    AutonomousProposalReviewIntegrityError,
    AutonomousProposalReviewStore,
)
from app.services.autonomous_proposal_store import (
    AutonomousProposalStore,
)


NOW = datetime(
    2026,
    8,
    6,
    14,
    40,
    tzinfo=timezone.utc,
)


def make_decision(
    tmp_path,
    *,
    proposal_id: str = (
        "proposal:review-store"
    ),
    review_decision_id: str = (
        "human-review:store"
    ),
    decision_type: (
        AutonomousHumanReviewDecisionType
    ) = (
        AutonomousHumanReviewDecisionType
        .APPROVED_FOR_AUTHORIZATION_REVIEW
    ),
):
    proposal_store = (
        AutonomousProposalStore(
            tmp_path
            / (
                f"{proposal_id.replace(':', '-')}-"
                f"{review_decision_id.replace(':', '-')}.db"
            )
        )
    )

    proposal = AutonomousOperationProposal(
        proposal_id=proposal_id,
        source_signal_id=(
            f"signal:{proposal_id}"
        ),
        decision_id=(
            f"decision:{proposal_id}"
        ),
        plan_id=(
            f"plan:{proposal_id}"
        ),
        target_node_id=(
            f"device:{proposal_id}"
        ),
        operation_type="disable_interface",
        summary="Review stored proposal",
        reason="Interface instability",
        confidence_percent=94,
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
        evaluated_confidence=94,
    )

    binding = AutonomousProposalBindingResult(
        proposal_id=proposal_id,
        decision_id=(
            f"decision:{proposal_id}"
        ),
        plan_id=(
            f"plan:{proposal_id}"
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

    proposal_store.append(
        proposal=proposal,
        policy=policy,
        binding=binding,
    )

    queue = (
        build_autonomous_proposal_review_queue(
            proposal_store,
            now=NOW,
        )
    )

    assert len(queue.items) == 1

    return create_autonomous_proposal_human_review(
        queue_item=queue.items[0],
        reviewer_id="reviewer:hani",
        reviewer_name="Hani Bahwal",
        decision=decision_type,
        reason="Reviewed manually",
        audit_id=queue.audit_id,
        audit_valid=True,
        reviewed_at=NOW,
        review_decision_id=(
            review_decision_id
        ),
    )


def test_append_and_get_review_decision(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    decision = make_decision(
        tmp_path
    )

    record = store.append(
        decision=decision
    )

    loaded = store.get(
        decision.review_decision_id
    )

    assert loaded == record
    assert record.sequence_number == 1

    assert (
        record.previous_record_hash
        == GENESIS_RECORD_HASH
    )

    assert record.verify_hash() is True
    assert record.can_execute is False


def test_record_contains_bound_identity(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    decision = make_decision(
        tmp_path
    )

    record = store.append(
        decision=decision
    )

    assert (
        record.review_decision_id
        == decision.review_decision_id
    )

    assert (
        record.decision_fingerprint
        == decision.decision_fingerprint
    )

    assert (
        record.proposal_record_hash
        == decision.record_hash
    )

    assert (
        record.decision
        == decision.decision.value
    )


def test_duplicate_review_id_rejected(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    decision = make_decision(
        tmp_path
    )

    store.append(
        decision=decision
    )

    with pytest.raises(
        AutonomousProposalReviewDuplicate,
    ):
        store.append(
            decision=decision
        )


def test_second_decision_for_same_proposal_rejected(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    first = make_decision(
        tmp_path,
        review_decision_id=(
            "human-review:first"
        ),
    )

    second = make_decision(
        tmp_path,
        review_decision_id=(
            "human-review:second"
        ),
        decision_type=(
            AutonomousHumanReviewDecisionType
            .REJECTED
        ),
    )

    store.append(
        decision=first
    )

    with pytest.raises(
        AutonomousProposalReviewDuplicate,
    ):
        store.append(
            decision=second
        )


def test_chain_links_multiple_records(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    first = make_decision(
        tmp_path,
        proposal_id="proposal:first",
        review_decision_id=(
            "human-review:first"
        ),
    )

    second = make_decision(
        tmp_path,
        proposal_id="proposal:second",
        review_decision_id=(
            "human-review:second"
        ),
        decision_type=(
            AutonomousHumanReviewDecisionType
            .CHANGES_REQUESTED
        ),
    )

    first_record = store.append(
        decision=first
    )

    second_record = store.append(
        decision=second
    )

    assert first_record.sequence_number == 1
    assert second_record.sequence_number == 2

    assert (
        second_record.previous_record_hash
        == first_record.record_hash
    )

    assert store.verify_chain() is True


def test_list_and_count(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    for number in range(
        1,
        4,
    ):
        decision = make_decision(
            tmp_path,
            proposal_id=(
                f"proposal:{number}"
            ),
            review_decision_id=(
                f"human-review:{number}"
            ),
        )

        store.append(
            decision=decision
        )

    records = store.list_records()

    assert store.count() == 3

    assert [
        record.sequence_number
        for record in records
    ] == [
        1,
        2,
        3,
    ]


def test_get_by_proposal_id(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    decision = make_decision(
        tmp_path
    )

    stored = store.append(
        decision=decision
    )

    loaded = store.get_by_proposal_id(
        decision.proposal_id
    )

    assert loaded == stored


def test_invalid_input_type_rejected(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    with pytest.raises(
        TypeError,
        match=(
            "AutonomousProposalHumanReviewDecision"
        ),
    ):
        store.append(
            decision="invalid"
        )


def test_tampered_payload_detected(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    decision = make_decision(
        tmp_path
    )

    store.append(
        decision=decision
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE
                autonomous_proposal_review_records
            SET decision_payload = ?
            WHERE review_decision_id = ?
            """,
            (
                '{"tampered":true}',
                decision.review_decision_id,
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousProposalReviewIntegrityError,
        match="hash mismatch",
    ):
        store.get(
            decision.review_decision_id
        )


def test_broken_previous_hash_detected(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "reviews.db"
    )

    store = AutonomousProposalReviewStore(
        database
    )

    first = make_decision(
        tmp_path,
        proposal_id="proposal:first",
        review_decision_id=(
            "human-review:first"
        ),
    )

    second = make_decision(
        tmp_path,
        proposal_id="proposal:second",
        review_decision_id=(
            "human-review:second"
        ),
    )

    store.append(
        decision=first
    )

    store.append(
        decision=second
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE
                autonomous_proposal_review_records
            SET previous_record_hash = ?
            WHERE sequence_number = 2
            """,
            (
                "f" * 64,
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousProposalReviewIntegrityError,
    ):
        store.verify_chain()


def test_record_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    decision = make_decision(
        tmp_path
    )

    record = store.append(
        decision=decision
    )

    payload = record.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "immutable_record": True,
        "append_only": True,
        "proposal_ledger_modified": False,
        "review_decision_modified": False,
        "approval_claim_created": False,
        "authorization_created": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
    }


def test_empty_store_chain_is_valid(
    tmp_path,
) -> None:
    store = AutonomousProposalReviewStore(
        tmp_path / "reviews.db"
    )

    assert store.count() == 0
    assert store.verify_chain() is True
