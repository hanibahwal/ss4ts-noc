from __future__ import annotations

from copy import deepcopy

import pytest

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionAuthorization,
    ExecutionRiskClass,
)
from app.models.execution_plan import (
    ExecutionStepType,
)
from app.services.execution_authorization import (
    ExecutionAuthorizationService,
    build_execution_authorization,
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


def test_build_returns_authorization() -> None:
    authorization = build_execution_authorization(
        make_plan(),
        requester=requester(),
    )

    assert isinstance(
        authorization,
        ExecutionAuthorization,
    )

    assert authorization.authorization_id
    assert authorization.plan_id
    assert authorization.decision_id


def test_mutating_plan_is_pending() -> None:
    authorization = build_execution_authorization(
        make_plan(),
        requester=requester(),
    )

    assert (
        authorization.status
        == AuthorizationStatus.PENDING
    )

    assert (
        authorization.decision
        == AuthorizationDecision.REQUIRE_APPROVAL
    )

    assert authorization.is_usable is False
    assert authorization.execution_allowed is False


def test_mutating_plan_requires_senior_role() -> None:
    authorization = build_execution_authorization(
        make_plan(),
        requester=requester(),
    )

    assert (
        authorization.risk_class
        == ExecutionRiskClass.MEDIUM
    )

    assert (
        authorization.metadata["required_role"]
        == "senior_engineer"
    )


def test_read_only_plan_is_approved() -> None:
    plan = make_plan()

    plan.steps = [
        step
        for step in plan.steps
        if (
            step.step_type
            != ExecutionStepType.COMMAND
        )
    ]

    authorization = build_execution_authorization(
        plan,
        requester=requester(),
    )

    assert (
        authorization.status
        == AuthorizationStatus.APPROVED
    )

    assert (
        authorization.decision
        == AuthorizationDecision.ALLOW
    )

    assert authorization.execution_allowed is True
    assert authorization.is_usable is True
    assert authorization.approver == authorization.requester


def test_unsafe_plan_is_rejected() -> None:
    plan = make_plan()

    command = next(
        step
        for step in plan.steps
        if (
            step.step_type
            == ExecutionStepType.COMMAND
        )
    )

    command.command = "/ip route disable 0"

    authorization = build_execution_authorization(
        plan,
        requester=requester(),
    )

    assert (
        authorization.status
        == AuthorizationStatus.REJECTED
    )

    assert (
        authorization.decision
        == AuthorizationDecision.DENY
    )

    assert authorization.rejection_reason
    assert authorization.execution_allowed is False


def test_critical_plan_is_rejected() -> None:
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
        clone = deepcopy(command)

        clone.step_id = f"command:{index}"
        clone.sequence = (
            len(plan.steps)
            + index
            + 1
        )

        plan.steps.append(clone)

    authorization = build_execution_authorization(
        plan,
        requester=requester(),
    )

    assert (
        authorization.risk_class
        == ExecutionRiskClass.CRITICAL
    )

    assert (
        authorization.status
        == AuthorizationStatus.REJECTED
    )


def test_authorization_expiry_is_configured() -> None:
    authorization = build_execution_authorization(
        make_plan(),
        requester=requester(),
        ttl_minutes=15,
    )

    delta = (
        authorization.expires_at
        - authorization.requested_at
    )

    assert int(
        delta.total_seconds()
    ) == 900


def test_authorization_is_safe() -> None:
    authorization = build_execution_authorization(
        make_plan(),
        requester=requester(),
    )

    assert (
        authorization.metadata["execution_enabled"]
        is False
    )

    assert (
        authorization.metadata["network_io_performed"]
        is False
    )

    assert (
        authorization.metadata["device_command_executed"]
        is False
    )


def test_authorization_serializes() -> None:
    authorization = build_execution_authorization(
        make_plan(),
        requester=requester(),
    )

    payload = authorization.to_dict()

    assert payload["authorization_id"]
    assert payload["requester"]
    assert payload["policy_reasons"]

    assert (
        payload["requires_human_approval"]
        is True
    )


def test_invalid_ttl_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="ttl_minutes",
    ):
        ExecutionAuthorizationService(
            ttl_minutes=0
        )


def test_invalid_plan_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="ExecutionPlan",
    ):
        build_execution_authorization(
            {},
            requester=requester(),
        )  # type: ignore[arg-type]


def test_invalid_requester_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="ApprovalIdentity",
    ):
        build_execution_authorization(
            make_plan(),
            requester={},
        )  # type: ignore[arg-type]
