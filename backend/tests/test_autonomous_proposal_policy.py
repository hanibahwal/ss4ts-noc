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
from app.services.autonomous_proposal_policy import (
    AutonomousProposalPolicy,
)


def make_proposal(
    **overrides,
) -> AutonomousOperationProposal:
    values = {
        "proposal_id":
            "autonomous-proposal:policy-1",
        "source_signal_id":
            "signal:wan-instability",
        "target_node_id":
            "device:core-router",
        "operation_type":
            "simulate_failover",
        "summary":
            "Evaluate WAN failover",
        "reason":
            "Primary WAN instability",
        "confidence_percent":
            92,
        "risk_level":
            AutonomousProposalRiskLevel
            .HIGH,
    }

    values.update(
        overrides
    )

    return AutonomousOperationProposal(
        **values
    )


def test_high_risk_proposal_is_allowed_for_review(
) -> None:
    policy = AutonomousProposalPolicy()

    result = policy.evaluate(
        make_proposal()
    )

    assert (
        result.policy_status
        is AutonomousPolicyStatus
        .ALLOWED_FOR_REVIEW
    )

    assert (
        result.operating_mode
        is AutonomousOperationMode
        .APPROVAL_CANDIDATE
    )

    assert result.allowed_for_review is True
    assert result.blocked is False
    assert result.requires_human_approval is True
    assert result.can_execute is False


def test_low_risk_proposal_is_advisory_only(
) -> None:
    policy = AutonomousProposalPolicy()

    result = policy.evaluate(
        make_proposal(
            risk_level=(
                AutonomousProposalRiskLevel
                .LOW
            )
        )
    )

    assert (
        result.operating_mode
        is AutonomousOperationMode
        .ADVISORY_ONLY
    )

    assert result.allowed_for_review is True
    assert result.blocked is False


def test_critical_risk_is_blocked(
) -> None:
    policy = AutonomousProposalPolicy()

    result = policy.evaluate(
        make_proposal(
            risk_level=(
                AutonomousProposalRiskLevel
                .CRITICAL
            )
        )
    )

    assert (
        result.policy_status
        is AutonomousPolicyStatus
        .BLOCKED
    )

    assert result.blocked is True
    assert result.allowed_for_review is False

    assert any(
        "Critical-risk" in reason
        for reason in result.reasons
    )


def test_low_confidence_is_blocked(
) -> None:
    policy = AutonomousProposalPolicy(
        minimum_confidence=75
    )

    result = policy.evaluate(
        make_proposal(
            confidence_percent=74
        )
    )

    assert result.blocked is True

    assert any(
        "below" in reason
        for reason in result.reasons
    )


def test_expired_proposal_is_blocked(
) -> None:
    now = datetime.now(
        timezone.utc
    )

    policy = AutonomousProposalPolicy()

    result = policy.evaluate(
        make_proposal(
            created_at=(
                now
                - timedelta(minutes=20)
            ),
            expires_at=(
                now
                - timedelta(minutes=1)
            ),
        )
    )

    assert result.blocked is True

    assert any(
        "expired" in reason
        for reason in result.reasons
    )


def test_policy_result_has_no_execution_authority(
) -> None:
    result = (
        AutonomousProposalPolicy()
        .evaluate(
            make_proposal()
        )
    )

    payload = result.to_dict()

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


def test_apply_updates_proposal_policy_fields(
) -> None:
    proposal = make_proposal()

    result = (
        AutonomousProposalPolicy()
        .apply(
            proposal
        )
    )

    assert (
        proposal.policy_status
        is result.policy_status
    )

    assert (
        proposal.operating_mode
        is result.operating_mode
    )

    assert (
        proposal.requires_human_approval
        is True
    )

    assert (
        proposal.policy_reasons
        == result.reasons
    )

    assert proposal.can_execute is False


def test_invalid_threshold_is_rejected(
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        AutonomousProposalPolicy(
            minimum_confidence=101
        )


def test_invalid_proposal_type_is_rejected(
) -> None:
    policy = AutonomousProposalPolicy()

    with pytest.raises(
        TypeError,
        match="AutonomousOperationProposal",
    ):
        policy.evaluate(
            "invalid"
        )


def test_multiple_block_reasons_are_preserved(
) -> None:
    now = datetime.now(
        timezone.utc
    )

    policy = AutonomousProposalPolicy(
        minimum_confidence=80
    )

    result = policy.evaluate(
        make_proposal(
            confidence_percent=50,
            risk_level=(
                AutonomousProposalRiskLevel
                .CRITICAL
            ),
            created_at=(
                now
                - timedelta(minutes=10)
            ),
            expires_at=(
                now
                - timedelta(minutes=1)
            ),
        )
    )

    assert result.blocked is True
    assert len(result.reasons) >= 3


@pytest.mark.parametrize(
    "minimum_confidence",
    [
        0,
        50,
        100,
    ],
)
def test_valid_confidence_thresholds(
    minimum_confidence: float,
) -> None:
    policy = AutonomousProposalPolicy(
        minimum_confidence=(
            minimum_confidence
        )
    )

    assert (
        policy.minimum_confidence
        == float(
            minimum_confidence
        )
    )
