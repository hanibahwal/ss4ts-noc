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
from app.models.decision_action import (
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
)
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBinding,
)
from app.services.decision_action_service import (
    DecisionActionService,
)
from tests.test_decision_action import (
    make_reversible_command,
    make_target,
)
from tests.test_execution_simulator import (
    make_plan,
)


def make_bound_objects():
    action_service = DecisionActionService()

    action = action_service.create_action(
        incident_id=(
            "incident:autonomous-binding"
        ),
        problem=(
            "Primary interface instability"
        ),
        recommendation=(
            "Disable unstable primary interface"
        ),
        confidence_percent=94,
        risk_level=(
            DecisionActionRiskLevel.HIGH
        ),
        execution_mode=(
            DecisionActionExecutionMode
            .APPROVAL_REQUIRED
        ),
        target=make_target(),
        command=make_reversible_command(),
        requested_by="autonomous-policy",
    )

    plan = make_plan()

    plan.decision_id = (
        action.decision_id
    )

    plan.source_node_id = (
        action.target.device_id
    )

    proposal = AutonomousOperationProposal(
        proposal_id=(
            "autonomous-proposal:binding-1"
        ),
        source_signal_id=(
            "signal:interface-instability"
        ),
        decision_id=action.decision_id,
        plan_id=plan.plan_id,
        target_node_id=(
            action.target.device_id
        ),
        operation_type=(
            action.command.action_type
        ),
        summary=(
            "Review controlled interface action"
        ),
        reason=(
            "Interface instability exceeded threshold"
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
    )

    return (
        proposal,
        action,
        plan,
    )


def test_valid_binding(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is True
    assert result.binding_errors == ()
    assert result.can_execute is False


def test_binding_result_has_no_execution_authority(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    payload = result.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "binding_validation_only": True,
        "execution_authority": False,
        "authorization_created": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
        "controlled_execution_required": True,
    }


def test_mismatched_decision_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.decision_id = (
        "decision:different"
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.decision_consistent is False


def test_mismatched_plan_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.plan_id = (
        "plan:different"
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.plan_consistent is False


def test_mismatched_target_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.target_node_id = (
        "device:different"
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.target_consistent is False


def test_mismatched_operation_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.operation_type = (
        "inspect_interface"
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.operation_consistent is False


def test_proposal_confidence_cannot_exceed_action(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.confidence_percent = 95

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.confidence_consistent is False


def test_proposal_cannot_understate_risk(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.risk_level = (
        AutonomousProposalRiskLevel.MEDIUM
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.risk_consistent is False


def test_blocked_policy_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.policy_status = (
        AutonomousPolicyStatus.BLOCKED
    )

    proposal.operating_mode = (
        AutonomousOperationMode
        .ADVISORY_ONLY
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.policy_review_allowed is False


def test_expired_proposal_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    now = datetime.now(
        timezone.utc
    )

    proposal.created_at = (
        now
        - timedelta(minutes=20)
    )

    proposal.expires_at = (
        now
        - timedelta(minutes=1)
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.proposal_not_expired is False


def test_missing_human_approval_boundary_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.operating_mode = (
        AutonomousOperationMode
        .ADVISORY_ONLY
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False

    assert (
        result.human_approval_required
        is False
    )


def test_non_dry_run_plan_is_rejected(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    plan.dry_run_only = False

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False
    assert result.dry_run_only is False


@pytest.mark.parametrize(
    (
        "argument",
        "value",
        "message",
    ),
    [
        (
            "proposal",
            "invalid",
            "AutonomousOperationProposal",
        ),
        (
            "action",
            "invalid",
            "DecisionAction",
        ),
        (
            "plan",
            "invalid",
            "ExecutionPlan",
        ),
    ],
)
def test_invalid_types_are_rejected(
    argument,
    value,
    message,
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    arguments = {
        "proposal": proposal,
        "action": action,
        "plan": plan,
    }

    arguments[argument] = value

    with pytest.raises(
        TypeError,
        match=message,
    ):
        AutonomousProposalBinding().validate(
            **arguments
        )


def test_multiple_binding_errors_are_preserved(
) -> None:
    proposal, action, plan = (
        make_bound_objects()
    )

    proposal.decision_id = (
        "decision:different"
    )

    proposal.plan_id = "plan:different"

    proposal.target_node_id = (
        "device:different"
    )

    proposal.operation_type = (
        "inspect_interface"
    )

    result = (
        AutonomousProposalBinding()
        .validate(
            proposal=proposal,
            action=action,
            plan=plan,
        )
    )

    assert result.binding_valid is False

    assert (
        len(
            result.binding_errors
        )
        >= 4
    )
