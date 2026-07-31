from __future__ import annotations

import pytest

from app.models.execution_plan import (
    ExecutionPlan,
    ExecutionPlanStatus,
    ExecutionPlanStep,
    ExecutionSafetyLevel,
    ExecutionStepStatus,
    ExecutionStepType,
    normalize_execution_plan,
)


def make_step(
    *,
    step_id: str = "step:1",
    sequence: int = 1,
    step_type: ExecutionStepType = (
        ExecutionStepType.VALIDATE
    ),
    command: str | None = None,
    rollback_command: str | None = None,
    safety_level: ExecutionSafetyLevel = (
        ExecutionSafetyLevel.READ_ONLY
    ),
    requires_approval: bool = False,
    automatic_allowed: bool = False,
    depends_on: list[str] | None = None,
) -> ExecutionPlanStep:
    return ExecutionPlanStep(
        step_id=step_id,
        sequence=sequence,
        step_type=step_type,
        title="Execution step",
        description="Perform a controlled network operation.",
        status=ExecutionStepStatus.PENDING,
        safety_level=safety_level,
        command=command,
        rollback_command=rollback_command,
        requires_approval=requires_approval,
        automatic_allowed=automatic_allowed,
        depends_on=depends_on or [],
        confidence_percent=90,
    )


def test_step_serialization() -> None:
    step = make_step()

    payload = step.to_dict()

    assert payload["id"] == "step:1"
    assert payload["type"] == "validate"
    assert payload["status"] == "pending"
    assert payload["confidence"] == 90.0
    assert payload["is_mutating"] is False


def test_command_step_requires_command() -> None:
    with pytest.raises(
        ValueError,
        match="requires a command",
    ):
        make_step(
            step_type=ExecutionStepType.COMMAND
        )


def test_high_risk_step_cannot_be_automatic() -> None:
    with pytest.raises(
        ValueError,
        match="cannot allow automatic",
    ):
        make_step(
            step_type=ExecutionStepType.COMMAND,
            command="/interface disable ether1",
            safety_level=(
                ExecutionSafetyLevel.HIGH_RISK
            ),
            automatic_allowed=True,
        )


def test_safe_automatic_read_only_step() -> None:
    step = make_step(
        automatic_allowed=True,
    )

    assert (
        step.is_safe_for_automatic_execution
        is True
    )


def test_plan_sorts_steps() -> None:
    plan = ExecutionPlan(
        plan_id="plan:1",
        source_node_id="device:core",
        decision_id="decision:1",
        title="Network recovery plan",
        summary="Recover service safely.",
        steps=[
            make_step(
                step_id="step:2",
                sequence=2,
            ),
            make_step(
                step_id="step:1",
                sequence=1,
            ),
        ],
    )

    assert [
        step.sequence
        for step in plan.steps
    ] == [1, 2]


def test_plan_statistics() -> None:
    plan = ExecutionPlan(
        plan_id="plan:1",
        source_node_id="device:core",
        decision_id="decision:1",
        title="Network recovery plan",
        summary="Recover service safely.",
        steps=[
            make_step(
                step_id="step:1",
                sequence=1,
            ),
            make_step(
                step_id="step:2",
                sequence=2,
                step_type=(
                    ExecutionStepType.COMMAND
                ),
                command="/interface enable ether1",
                rollback_command=(
                    "/interface disable ether1"
                ),
                safety_level=(
                    ExecutionSafetyLevel.MEDIUM_RISK
                ),
                requires_approval=True,
                depends_on=["step:1"],
            ),
        ],
    )

    payload = plan.to_dict()

    assert (
        payload["statistics"]
        ["step_count"]
        == 2
    )

    assert (
        payload["statistics"]
        ["mutating_step_count"]
        == 1
    )

    assert (
        payload["statistics"]
        ["rollback_available"]
        is True
    )

    assert (
        payload["approval_required"]
        is True
    )


def test_unknown_dependency_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="unknown dependency",
    ):
        ExecutionPlan(
            plan_id="plan:1",
            source_node_id="device:core",
            decision_id="decision:1",
            title="Network recovery plan",
            summary="Recover service safely.",
            steps=[
                make_step(
                    depends_on=["step:missing"]
                ),
            ],
        )


def test_duplicate_sequences_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate sequences",
    ):
        ExecutionPlan(
            plan_id="plan:1",
            source_node_id="device:core",
            decision_id="decision:1",
            title="Network recovery plan",
            summary="Recover service safely.",
            steps=[
                make_step(
                    step_id="step:1",
                    sequence=1,
                ),
                make_step(
                    step_id="step:2",
                    sequence=1,
                ),
            ],
        )


def test_approved_plan_requires_approver() -> None:
    with pytest.raises(
        ValueError,
        match="approved_by",
    ):
        ExecutionPlan(
            plan_id="plan:1",
            source_node_id="device:core",
            decision_id="decision:1",
            title="Network recovery plan",
            summary="Recover service safely.",
            approved=True,
        )


def test_dry_run_plan_cannot_auto_execute() -> None:
    with pytest.raises(
        ValueError,
        match="Dry-run-only",
    ):
        ExecutionPlan(
            plan_id="plan:1",
            source_node_id="device:core",
            decision_id="decision:1",
            title="Network recovery plan",
            summary="Recover service safely.",
            dry_run_only=True,
            automatic_execution_allowed=True,
        )


def test_plan_from_dict() -> None:
    plan = ExecutionPlan.from_dict({
        "id": "plan:1",
        "source": "device:core",
        "decision_id": "decision:1",
        "title": "Recovery plan",
        "description": "Controlled recovery workflow.",
        "status": "proposed",
        "steps": [
            {
                "id": "step:1",
                "order": 1,
                "type": "validate",
                "title": "Validate device",
                "summary": "Check current device state.",
            },
        ],
    })

    assert (
        plan.status
        == ExecutionPlanStatus.PROPOSED
    )

    assert plan.step_count == 1


def test_normalize_execution_plan() -> None:
    plan = normalize_execution_plan({
        "id": "plan:1",
        "source": "device:core",
        "decision_id": "decision:1",
        "title": "Recovery plan",
        "summary": "Controlled recovery workflow.",
        "steps": [],
    })

    assert isinstance(
        plan,
        ExecutionPlan,
    )


def test_normalize_invalid_plan() -> None:
    assert (
        normalize_execution_plan(
            "invalid"
        )
        is None
    )
