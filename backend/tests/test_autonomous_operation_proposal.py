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
    normalize_autonomous_operation_proposal,
)


def make_proposal(
    **overrides,
) -> AutonomousOperationProposal:
    values = {
        "proposal_id":
            "autonomous-proposal:1",
        "source_signal_id":
            "signal:wan-instability",
        "decision_id":
            "decision:wan-instability",
        "plan_id":
            "execution-plan:wan-instability",
        "target_node_id":
            "device:core-router",
        "operation_type":
            "simulate_failover",
        "summary":
            "Evaluate controlled WAN failover",
        "reason":
            "Primary WAN instability detected",
        "confidence_percent":
            94,
        "risk_level":
            AutonomousProposalRiskLevel.HIGH,
        "policy_status":
            AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW,
        "operating_mode":
            AutonomousOperationMode
            .APPROVAL_CANDIDATE,
        "requires_human_approval":
            True,
        "idempotency_key":
            "wan-instability:device:core-router",
        "evidence_references": (
            "evidence:latency",
            "evidence:packet-loss",
        ),
        "policy_reasons": (
            "High-risk network change",
            "Human approval required",
        ),
    }

    values.update(
        overrides
    )

    return AutonomousOperationProposal(
        **values
    )


def test_proposal_serialization(
) -> None:
    proposal = make_proposal()

    payload = proposal.to_dict()

    assert (
        payload["proposal_id"]
        == "autonomous-proposal:1"
    )

    assert (
        payload["operating_mode"]
        == "approval_candidate"
    )

    assert (
        payload["policy_status"]
        == "allowed_for_review"
    )

    assert payload["can_execute"] is False

    assert (
        payload["safety"][
            "execution_authority"
        ]
        is False
    )

    assert (
        payload["safety"][
            "network_io_performed"
        ]
        is False
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_proposal_is_never_execution_authority(
) -> None:
    proposal = make_proposal()

    assert proposal.can_execute is False


def test_default_mode_is_advisory_only(
) -> None:
    proposal = AutonomousOperationProposal(
        source_signal_id="signal:1",
        target_node_id="device:1",
        operation_type="analyze_cpu",
        summary="Analyze CPU pressure",
        reason="Sustained CPU increase",
        confidence_percent=80,
        risk_level=(
            AutonomousProposalRiskLevel
            .MEDIUM
        ),
    )

    assert (
        proposal.operating_mode
        is AutonomousOperationMode
        .ADVISORY_ONLY
    )

    assert (
        proposal.policy_status
        is AutonomousPolicyStatus
        .PENDING_EVALUATION
    )

    assert (
        proposal.requires_human_approval
        is True
    )


def test_approval_candidate_requires_human_approval(
) -> None:
    with pytest.raises(
        ValueError,
        match="human approval",
    ):
        make_proposal(
            requires_human_approval=False
        )


@pytest.mark.parametrize(
    "risk_level",
    [
        AutonomousProposalRiskLevel.HIGH,
        AutonomousProposalRiskLevel.CRITICAL,
    ],
)
def test_high_risk_requires_human_approval(
    risk_level,
) -> None:
    with pytest.raises(
        ValueError,
        match="human approval",
    ):
        make_proposal(
            risk_level=risk_level,
            operating_mode=(
                AutonomousOperationMode
                .ADVISORY_ONLY
            ),
            requires_human_approval=False,
        )


def test_blocked_proposal_must_remain_advisory(
) -> None:
    with pytest.raises(
        ValueError,
        match="advisory-only",
    ):
        make_proposal(
            policy_status=(
                AutonomousPolicyStatus
                .BLOCKED
            ),
            operating_mode=(
                AutonomousOperationMode
                .APPROVAL_CANDIDATE
            ),
        )


@pytest.mark.parametrize(
    "operation_type",
    [
        "AUTO_EXECUTE",
        "execute_now",
        "bypass_approval",
        "device_command",
        "routeros_command",
    ],
)
def test_forbidden_execution_operations_are_rejected(
    operation_type: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="forbidden",
    ):
        make_proposal(
            operation_type=operation_type
        )


def test_confidence_must_be_in_range(
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        make_proposal(
            confidence_percent=101
        )


def test_expiry_must_be_after_creation(
) -> None:
    now = datetime.now(
        timezone.utc
    )

    with pytest.raises(
        ValueError,
        match="after created_at",
    ):
        make_proposal(
            created_at=now,
            expires_at=(
                now
                - timedelta(seconds=1)
            ),
        )


def test_expired_proposal_is_not_reviewable(
) -> None:
    now = datetime.now(
        timezone.utc
    )

    proposal = make_proposal(
        created_at=(
            now
            - timedelta(minutes=10)
        ),
        expires_at=(
            now
            - timedelta(minutes=1)
        ),
    )

    assert proposal.is_expired is True
    assert proposal.review_allowed is False
    assert proposal.can_execute is False


def test_allowed_non_expired_proposal_is_reviewable(
) -> None:
    now = datetime.now(
        timezone.utc
    )

    proposal = make_proposal(
        created_at=now,
        expires_at=(
            now
            + timedelta(minutes=30)
        ),
    )

    assert proposal.is_expired is False
    assert proposal.review_allowed is True


def test_evidence_and_policy_reasons_are_deduplicated(
) -> None:
    proposal = make_proposal(
        evidence_references=(
            "evidence:1",
            "evidence:1",
            "evidence:2",
        ),
        policy_reasons=(
            "Approval required",
            "Approval required",
            "Rollback required",
        ),
    )

    assert proposal.evidence_references == (
        "evidence:1",
        "evidence:2",
    )

    assert proposal.policy_reasons == (
        "Approval required",
        "Rollback required",
    )


def test_fingerprint_is_deterministic(
) -> None:
    created_at = datetime(
        2026,
        8,
        6,
        11,
        30,
        tzinfo=timezone.utc,
    )

    first = make_proposal(
        created_at=created_at
    )

    second = make_proposal(
        created_at=created_at
    )

    assert (
        first.fingerprint
        == second.fingerprint
    )


def test_fingerprint_changes_when_proposal_changes(
) -> None:
    created_at = datetime(
        2026,
        8,
        6,
        11,
        30,
        tzinfo=timezone.utc,
    )

    first = make_proposal(
        created_at=created_at
    )

    second = make_proposal(
        created_at=created_at,
        confidence_percent=93,
    )

    assert (
        first.fingerprint
        != second.fingerprint
    )


def test_normalize_dictionary(
) -> None:
    normalized = (
        normalize_autonomous_operation_proposal({
            "proposal_id":
                "autonomous-proposal:normalized",
            "source_signal_id":
                "signal:normalized",
            "target_node_id":
                "device:normalized",
            "operation_type":
                "analyze_link",
            "summary":
                "Analyze unstable link",
            "reason":
                "Packet loss exceeded threshold",
            "confidence":
                87,
            "risk_level":
                "medium",
            "policy_status":
                "allowed_for_review",
            "operating_mode":
                "advisory_only",
        })
    )

    assert normalized is not None

    assert (
        normalized.confidence_percent
        == 87
    )

    assert (
        normalized.risk_level
        is AutonomousProposalRiskLevel
        .MEDIUM
    )


def test_normalize_invalid_value_returns_none(
) -> None:
    assert (
        normalize_autonomous_operation_proposal(
            "invalid"
        )
        is None
    )


def test_normalize_forbidden_operation_returns_none(
) -> None:
    normalized = (
        normalize_autonomous_operation_proposal({
            "source_signal_id":
                "signal:1",
            "target_node_id":
                "device:1",
            "operation_type":
                "AUTO_EXECUTE",
            "summary":
                "Unsafe operation",
            "reason":
                "Unsafe",
            "confidence":
                100,
            "risk_level":
                "critical",
        })
    )

    assert normalized is None
