from __future__ import annotations

import pytest

from app.models.execution_plan import (
    ExecutionPlan,
    ExecutionPlanStep,
    ExecutionSafetyLevel,
    ExecutionStepType,
)
from app.models.execution_simulation import (
    SimulatedStepOutcome,
    SimulationStatus,
)
from app.services.execution_simulator import (
    ExecutionSimulator,
    simulate_execution_plan,
)


def make_plan() -> ExecutionPlan:
    source = "device:core"

    return ExecutionPlan(
        plan_id="execution-plan:device:core",
        source_node_id=source,
        decision_id="decision:core",
        title="Safe recovery plan",
        summary="Dry-run recovery workflow.",
        steps=[
            ExecutionPlanStep(
                step_id="step:1",
                sequence=1,
                step_type=
                    ExecutionStepType.OBSERVE,
                title="Observe state",
                description="Capture current state.",
                automatic_allowed=True,
            ),
            ExecutionPlanStep(
                step_id="step:2",
                sequence=2,
                step_type=
                    ExecutionStepType.APPROVAL,
                title="Approval gate",
                description="Require approval.",
                requires_approval=True,
                automatic_allowed=False,
                depends_on=["step:1"],
            ),
            ExecutionPlanStep(
                step_id="step:3",
                sequence=3,
                step_type=
                    ExecutionStepType.COMMAND,
                title="Dry-run action",
                description="Simulate action.",
                command=(
                    "DRY_RUN_ONLY: enable backup"
                ),
                rollback_command=(
                    "DRY_RUN_ONLY: restore primary"
                ),
                safety_level=(
                    ExecutionSafetyLevel.MEDIUM_RISK
                ),
                requires_approval=True,
                automatic_allowed=False,
                depends_on=["step:2"],
            ),
            ExecutionPlanStep(
                step_id="step:4",
                sequence=4,
                step_type=
                    ExecutionStepType.VERIFY,
                title="Verify service",
                description="Verify service health.",
                automatic_allowed=True,
                depends_on=["step:3"],
            ),
        ],
        dry_run_only=True,
        automatic_execution_allowed=False,
    )


def test_simulation_blocks_without_approval() -> None:
    result = simulate_execution_plan(
        make_plan(),
        approval_granted=False,
    )

    assert (
        result.status
        == SimulationStatus.BLOCKED
    )

    assert result.steps[0].outcome == (
        SimulatedStepOutcome.SUCCESS
    )

    assert result.steps[1].outcome == (
        SimulatedStepOutcome.BLOCKED
    )


def test_simulation_completes_with_approval() -> None:
    result = simulate_execution_plan(
        make_plan(),
        approval_granted=True,
    )

    assert (
        result.status
        == SimulationStatus.COMPLETED
    )

    assert result.step_count == 4
    assert result.successful_step_count == 4
    assert result.failed_step_count == 0


def test_command_is_never_executed() -> None:
    result = simulate_execution_plan(
        make_plan(),
        approval_granted=True,
    )

    command = result.steps[2]

    assert command.outcome == (
        SimulatedStepOutcome.SUCCESS
    )

    assert "no device command" in (
        command.message.lower()
    )

    assert (
        result.metadata["execution_enabled"]
        is False
    )


def test_failure_before_command_has_no_rollback() -> None:
    result = simulate_execution_plan(
        make_plan(),
        approval_granted=True,
        fail_step_ids={"step:1"},
    )

    assert (
        result.status
        == SimulationStatus.FAILED
    )

    assert result.rollback_performed is False
    assert result.failure_step_id == "step:1"


def test_verification_failure_triggers_rollback() -> None:
    result = simulate_execution_plan(
        make_plan(),
        approval_granted=True,
        fail_step_ids={"step:4"},
    )

    assert (
        result.status
        == SimulationStatus.ROLLED_BACK
    )

    assert result.rollback_performed is True
    assert result.failure_step_id == "step:4"

    command = next(
        step
        for step in result.steps
        if step.step_id == "step:3"
    )

    assert command.rollback_attempted is True
    assert command.rollback_succeeded is True

    assert command.outcome == (
        SimulatedStepOutcome.ROLLED_BACK
    )


def test_result_serializes() -> None:
    result = simulate_execution_plan(
        make_plan(),
        approval_granted=True,
    )

    payload = result.to_dict()

    assert payload["dry_run"] is True

    assert (
        payload["statistics"]
        ["step_count"]
        == 4
    )

    assert (
        payload["statistics"]
        ["successful_step_count"]
        == 4
    )


def test_non_dry_run_plan_rejected() -> None:
    plan = make_plan()
    plan.dry_run_only = False

    simulator = ExecutionSimulator(
        approval_granted=True
    )

    with pytest.raises(
        ValueError,
        match="dry-run",
    ):
        simulator.simulate(plan)


def test_invalid_plan_type_rejected() -> None:
    simulator = ExecutionSimulator()

    with pytest.raises(
        TypeError,
        match="ExecutionPlan",
    ):
        simulator.simulate({})  # type: ignore[arg-type]
