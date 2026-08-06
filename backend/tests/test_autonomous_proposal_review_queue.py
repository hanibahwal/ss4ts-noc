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
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBindingResult,
)
from app.services.autonomous_proposal_policy import (
    AutonomousProposalPolicyResult,
)
from app.services.autonomous_proposal_review_queue import (
    AutonomousProposalReviewQueue,
    AutonomousReviewStatus,
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


def make_proposal(
    proposal_id: str,
    *,
    risk_level: AutonomousProposalRiskLevel = (
        AutonomousProposalRiskLevel.HIGH
    ),
    confidence_percent: float = 90,
    created_at: datetime | None = None,
    expires_at: datetime | None = None,
    requires_human_approval: bool = True,
) -> AutonomousOperationProposal:
    return AutonomousOperationProposal(
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
        summary=(
            f"Review {proposal_id}"
        ),
        reason="Interface instability",
        confidence_percent=(
            confidence_percent
        ),
        risk_level=risk_level,
        policy_status=(
            AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
        ),
        operating_mode=(
            AutonomousOperationMode
            .APPROVAL_CANDIDATE
        ),
        requires_human_approval=(
            requires_human_approval
        ),
        created_at=(
            created_at
            or NOW
            - timedelta(hours=1)
        ),
        expires_at=(
            expires_at
            or NOW
            + timedelta(hours=1)
        ),
    )


def make_policy(
    proposal_id: str,
    *,
    allowed_for_review: bool = True,
    blocked: bool = False,
) -> AutonomousProposalPolicyResult:
    return AutonomousProposalPolicyResult(
        proposal_id=proposal_id,
        policy_status=(
            AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
            if allowed_for_review
            else AutonomousPolicyStatus
            .BLOCKED
        ),
        operating_mode=(
            AutonomousOperationMode
            .APPROVAL_CANDIDATE
            if allowed_for_review
            else AutonomousOperationMode
            .ADVISORY_ONLY
        ),
        requires_human_approval=True,
        allowed_for_review=(
            allowed_for_review
        ),
        blocked=blocked,
        reasons=(
            "Human approval required",
        ),
        confidence_threshold=70,
        evaluated_confidence=90,
    )


def make_binding(
    proposal_id: str,
    *,
    binding_valid: bool = True,
    proposal_not_expired: bool = True,
    human_approval_required: bool = True,
    dry_run_only: bool = True,
) -> AutonomousProposalBindingResult:
    return AutonomousProposalBindingResult(
        proposal_id=proposal_id,
        decision_id=(
            f"decision:{proposal_id}"
        ),
        plan_id=(
            f"plan:{proposal_id}"
        ),
        binding_valid=binding_valid,
        binding_errors=(
            ()
            if binding_valid
            else (
                "Invalid binding",
            )
        ),
        decision_consistent=True,
        plan_consistent=True,
        target_consistent=True,
        operation_consistent=True,
        confidence_consistent=True,
        risk_consistent=True,
        policy_review_allowed=True,
        proposal_not_expired=(
            proposal_not_expired
        ),
        human_approval_required=(
            human_approval_required
        ),
        dry_run_only=dry_run_only,
    )


def append_proposal(
    store: AutonomousProposalStore,
    proposal_id: str,
    *,
    proposal=None,
    policy=None,
    binding=None,
) -> None:
    store.append(
        proposal=(
            proposal
            or make_proposal(
                proposal_id
            )
        ),
        policy=(
            policy
            or make_policy(
                proposal_id
            )
        ),
        binding=(
            binding
            or make_binding(
                proposal_id
            )
        ),
    )


def test_eligible_proposal_appears_in_queue(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    append_proposal(
        store,
        "proposal:eligible",
    )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert result.audit_valid is True
    assert result.source_record_count == 1
    assert result.eligible_record_count == 1
    assert result.excluded_record_count == 0
    assert len(result.items) == 1

    item = result.items[0]

    assert (
        item.proposal_id
        == "proposal:eligible"
    )

    assert (
        item.review_status
        is AutonomousReviewStatus
        .PENDING_REVIEW
    )

    assert item.review_required is True
    assert item.can_execute is False


@pytest.mark.parametrize(
    "policy,binding,proposal",
    [
        (
            make_policy(
                "proposal:blocked",
                allowed_for_review=False,
                blocked=True,
            ),
            make_binding(
                "proposal:blocked",
            ),
            make_proposal(
                "proposal:blocked"
            ),
        ),
        (
            make_policy(
                "proposal:binding",
            ),
            make_binding(
                "proposal:binding",
                binding_valid=False,
            ),
            make_proposal(
                "proposal:binding"
            ),
        ),
        (
            make_policy(
                "proposal:expired-check",
            ),
            make_binding(
                "proposal:expired-check",
                proposal_not_expired=False,
            ),
            make_proposal(
                "proposal:expired-check"
            ),
        ),
        (
            make_policy(
                "proposal:no-approval",
            ),
            make_binding(
                "proposal:no-approval",
                human_approval_required=False,
            ),
            make_proposal(
                "proposal:no-approval"
            ),
        ),
        (
            make_policy(
                "proposal:not-dry",
            ),
            make_binding(
                "proposal:not-dry",
                dry_run_only=False,
            ),
            make_proposal(
                "proposal:not-dry"
            ),
        ),
    ],
)
def test_ineligible_records_are_excluded(
    tmp_path,
    policy,
    binding,
    proposal,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    store.append(
        proposal=proposal,
        policy=policy,
        binding=binding,
    )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert result.eligible_record_count == 0
    assert result.excluded_record_count == 1
    assert result.items == ()


def test_expired_timestamp_is_excluded(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    proposal_id = "proposal:expired-time"

    append_proposal(
        store,
        proposal_id,
        proposal=make_proposal(
            proposal_id,
            expires_at=(
                NOW
                - timedelta(seconds=1)
            ),
        ),
    )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert result.items == ()


def test_priority_orders_risk_first(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    append_proposal(
        store,
        "proposal:medium",
        proposal=make_proposal(
            "proposal:medium",
            risk_level=(
                AutonomousProposalRiskLevel
                .MEDIUM
            ),
            confidence_percent=99,
        ),
    )

    append_proposal(
        store,
        "proposal:high",
        proposal=make_proposal(
            "proposal:high",
            risk_level=(
                AutonomousProposalRiskLevel
                .HIGH
            ),
            confidence_percent=70,
        ),
    )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert [
        item.proposal_id
        for item in result.items
    ] == [
        "proposal:high",
        "proposal:medium",
    ]


def test_same_risk_orders_confidence(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    append_proposal(
        store,
        "proposal:confidence-80",
        proposal=make_proposal(
            "proposal:confidence-80",
            confidence_percent=80,
        ),
    )

    append_proposal(
        store,
        "proposal:confidence-95",
        proposal=make_proposal(
            "proposal:confidence-95",
            confidence_percent=95,
        ),
    )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert (
        result.items[0].proposal_id
        == "proposal:confidence-95"
    )


def test_age_increases_priority(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    append_proposal(
        store,
        "proposal:new",
        proposal=make_proposal(
            "proposal:new",
            created_at=(
                NOW
                - timedelta(hours=1)
            ),
        ),
    )

    append_proposal(
        store,
        "proposal:old",
        proposal=make_proposal(
            "proposal:old",
            created_at=(
                NOW
                - timedelta(hours=10)
            ),
        ),
    )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert (
        result.items[0].proposal_id
        == "proposal:old"
    )


def test_limit_is_applied_after_priority_sort(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    for number in range(
        1,
        4,
    ):
        proposal_id = (
            f"proposal:limit-{number}"
        )

        append_proposal(
            store,
            proposal_id,
            proposal=make_proposal(
                proposal_id,
                confidence_percent=(
                    70
                    + number
                ),
            ),
        )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            limit=2,
            now=NOW,
        )
    )

    assert len(result.items) == 2
    assert result.eligible_record_count == 3


def test_failed_audit_suppresses_queue(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "autonomous.db"
    )

    store = AutonomousProposalStore(
        database
    )

    append_proposal(
        store,
        "proposal:tampered",
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_proposal_records
            SET proposal_payload = ?
            WHERE proposal_id = ?
            """,
            (
                '{"tampered":true}',
                "proposal:tampered",
            ),
        )

        connection.commit()

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    assert result.audit_valid is False
    assert result.items == ()

    assert (
        "audit failed"
        in result.warnings[0]
    )


def test_queue_does_not_modify_store(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    append_proposal(
        store,
        "proposal:read-only",
    )

    before = store.count()

    build_autonomous_proposal_review_queue(
        store,
        now=NOW,
    )

    after = store.count()

    assert before == after == 1


def test_queue_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousProposalStore(
        tmp_path / "autonomous.db"
    )

    result = (
        build_autonomous_proposal_review_queue(
            store,
            now=NOW,
        )
    )

    payload = result.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "read_only_projection": True,
        "database_write_performed": False,
        "approval_decision_created": False,
        "authorization_created": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
        "automatic_execution_allowed": False,
    }


def test_invalid_store_type_is_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match="AutonomousProposalStore",
    ):
        AutonomousProposalReviewQueue(
            "invalid"
        )
