from __future__ import annotations

from copy import deepcopy

import pytest

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationDecision,
    ExecutionRiskClass,
)
from app.models.execution_plan import (
    ExecutionStepType,
)
from app.services.execution_safety_policy import (
    ExecutionPolicyResult,
    ExecutionSafetyPolicy,
    evaluate_execution_policy,
)
from tests.test_execution_simulator import (
    make_plan,
)


def requester() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:hani",
        display_name="Hani",
        role=ApprovalRole.NETWORK_ENGINEER,
    )


def test_policy_returns_result() -> None:
    result = evaluate_execution_policy(
        make_plan(),
        requester=requester(),
    )

    assert isinstance(
        result,
        ExecutionPolicyResult,
    )


def test_mutating_plan_requires_approval() -> None:
    result = evaluate_execution_policy(
        make_plan(),
        requester=requester(),
    )

    assert (
        result.decision
        == AuthorizationDecision
        .REQUIRE_APPROVAL
    )

    assert result.approval_required is True
    assert result.dry_run_required is True
    assert result.execution_allowed is False

    assert (
        result.risk_class
        == ExecutionRiskClass.MEDIUM
    )

    assert (
        result.required_role
        == ApprovalRole.SENIOR_ENGINEER
    )


def test_read_only_plan_is_allowed() -> None:
    plan = make_plan()

    plan.steps = [
        step
        for step in plan.steps
        if (
            step.step_type
            != ExecutionStepType.COMMAND
        )
    ]

    result = evaluate_execution_policy(
        plan,
        requester=requester(),
    )

    assert (
        result.decision
        == AuthorizationDecision.ALLOW
    )

    assert (
        result.risk_class
        == ExecutionRiskClass.READ_ONLY
    )

    assert result.execution_allowed is True
    assert result.approval_required is False


def test_unsafe_command_is_denied() -> None:
    plan = make_plan()

    command = next(
        step
        for step in plan.steps
        if (
            step.step_type
            == ExecutionStepType.COMMAND
        )
    )

    command.command = (
        "/ip route disable 0"
    )

    result = evaluate_execution_policy(
        plan,
        requester=requester(),
    )

    assert (
        result.decision
        == AuthorizationDecision.DENY
    )

    assert any(
        "Unsafe command" in reason
        for reason in result.reasons
    )


def test_missing_rollback_is_denied() -> None:
    plan = make_plan()

    command = next(
        step
        for step in plan.steps
        if (
            step.step_type
            == ExecutionStepType.COMMAND
        )
    )

    command.rollback_command = None
    command.reversible = False

    result = evaluate_execution_policy(
        plan,
        requester=requester(),
    )

    assert (
        result.decision
        == AuthorizationDecision.DENY
    )

    assert any(
        "rollback" in reason.lower()
        for reason in result.reasons
    )


def test_missing_verification_is_denied() -> None:
    plan = make_plan()

    plan.steps = [
        step
        for step in plan.steps
        if (
            step.step_type
            != ExecutionStepType.VERIFY
        )
    ]

    result = evaluate_execution_policy(
        plan,
        requester=requester(),
    )

    assert (
        result.decision
        == AuthorizationDecision.DENY
    )

    assert any(
        "verification" in reason.lower()
        for reason in result.reasons
    )


def test_critical_plan_is_denied() -> None:
    plan = make_plan()

    command = next(
        step
        for step in plan.steps
        if (
            step.step_type
            == ExecutionStepType.COMMAND
        )
    )

    for index in range(4):
        clone = deepcopy(
            command
        )

        clone.step_id = (
            f"command:{index}"
        )

        clone.sequence = (
            len(plan.steps)
            + index
            + 1
        )

        plan.steps.append(
            clone
        )

    result = evaluate_execution_policy(
        plan,
        requester=requester(),
    )

    assert (
        result.risk_class
        == ExecutionRiskClass.CRITICAL
    )

    assert (
        result.decision
        == AuthorizationDecision.DENY
    )

    assert result.execution_allowed is False


def test_reasons_are_serialized() -> None:
    result = evaluate_execution_policy(
        make_plan(),
        requester=requester(),
    )

    payload = result.to_dict()

    assert payload["reasons"]
    assert (
        payload["required_role"]
        == "senior_engineer"
    )


def test_invalid_plan_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="ExecutionPlan",
    ):
        evaluate_execution_policy(
            {},
            requester=requester(),
        )  # type: ignore[arg-type]


def test_invalid_requester_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="ApprovalIdentity",
    ):
        ExecutionSafetyPolicy().evaluate(
            make_plan(),
            requester={},
        )  # type: ignore[arg-type]
