from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Iterable

from app.models.execution_plan import (
    ExecutionPlan,
    ExecutionPlanStep,
    ExecutionStepType,
)
from app.models.execution_simulation import (
    ExecutionSimulationResult,
    SimulatedStepOutcome,
    SimulatedStepResult,
    SimulationStatus,
)


class ExecutionSimulator:
    """
    Simulate an execution plan without network I/O.

    Commands are never executed. The simulator only validates order,
    dependencies, approval gates, verification and rollback behavior.
    """

    def __init__(
        self,
        *,
        approval_granted: bool = False,
        fail_step_ids: (
            Iterable[str] | None
        ) = None,
    ) -> None:
        self.approval_granted = (
            approval_granted
        )

        self.fail_step_ids = set(
            fail_step_ids or []
        )

    @staticmethod
    def _dependencies_succeeded(
        step: ExecutionPlanStep,
        outcomes: dict[
            str,
            SimulatedStepOutcome,
        ],
    ) -> bool:
        return all(
            outcomes.get(
                dependency
            )
            == SimulatedStepOutcome.SUCCESS
            for dependency in step.depends_on
        )

    def _simulate_step(
        self,
        step: ExecutionPlanStep,
        outcomes: dict[
            str,
            SimulatedStepOutcome,
        ],
    ) -> SimulatedStepResult:
        started_at = datetime.now(
            timezone.utc
        )
        started_clock = perf_counter()

        outcome = (
            SimulatedStepOutcome.SUCCESS
        )
        message = (
            "Step simulated successfully."
        )

        if not self._dependencies_succeeded(
            step,
            outcomes,
        ):
            outcome = (
                SimulatedStepOutcome.BLOCKED
            )
            message = (
                "Step blocked because one or "
                "more dependencies did not succeed."
            )

        elif (
            step.step_type
            == ExecutionStepType.APPROVAL
            and not self.approval_granted
        ):
            outcome = (
                SimulatedStepOutcome.BLOCKED
            )
            message = (
                "Approval gate blocked the plan."
            )

        elif (
            step.requires_approval
            and not self.approval_granted
        ):
            outcome = (
                SimulatedStepOutcome.BLOCKED
            )
            message = (
                "Step requires engineer approval."
            )

        elif step.step_id in self.fail_step_ids:
            outcome = (
                SimulatedStepOutcome.FAILED
            )
            message = (
                "Configured simulation failure "
                "was triggered for this step."
            )

        elif (
            step.step_type
            == ExecutionStepType.COMMAND
        ):
            if not step.command:
                outcome = (
                    SimulatedStepOutcome.FAILED
                )
                message = (
                    "Command step has no command."
                )
            elif not step.command.startswith(
                "DRY_RUN_ONLY:"
            ):
                outcome = (
                    SimulatedStepOutcome.BLOCKED
                )
                message = (
                    "Unsafe command rejected: "
                    "DRY_RUN_ONLY prefix missing."
                )
            else:
                message = (
                    "Dry-run command accepted; "
                    "no device command was executed."
                )

        completed_at = datetime.now(
            timezone.utc
        )

        duration_ms = (
            perf_counter()
            - started_clock
        ) * 1000.0

        return SimulatedStepResult(
            step_id=step.step_id,
            sequence=step.sequence,
            title=step.title,
            step_type=
                step.step_type.value,
            outcome=outcome,
            message=message,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            metadata={
                "requires_approval":
                    step.requires_approval,
                "automatic_allowed":
                    step.automatic_allowed,
                "safety_level":
                    step.safety_level.value,
                "depends_on":
                    list(step.depends_on),
            },
        )

    @staticmethod
    def _rollback(
        plan: ExecutionPlan,
        result: ExecutionSimulationResult,
    ) -> None:
        mutating_results = {
            step.step_id: step
            for step in result.steps
            if step.step_type
            == ExecutionStepType.COMMAND.value
            and step.outcome
            == SimulatedStepOutcome.SUCCESS
        }

        if not mutating_results:
            return

        for step in reversed(
            plan.steps
        ):
            simulated = (
                mutating_results.get(
                    step.step_id
                )
            )

            if simulated is None:
                continue

            simulated.rollback_attempted = True

            if (
                step.reversible
                and step.rollback_command
                and step.rollback_command
                .startswith("DRY_RUN_ONLY:")
            ):
                simulated.rollback_succeeded = True
                simulated.outcome = (
                    SimulatedStepOutcome
                    .ROLLED_BACK
                )
                simulated.message = (
                    "Dry-run rollback simulated "
                    "successfully."
                )

                result.rollback_performed = True

    def simulate(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionSimulationResult:
        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "ExecutionSimulator requires "
                "an ExecutionPlan"
            )

        if not plan.dry_run_only:
            raise ValueError(
                "Simulator accepts dry-run plans only"
            )

        started_at = datetime.now(
            timezone.utc
        )

        simulation = (
            ExecutionSimulationResult(
                simulation_id=(
                    f"simulation:{plan.plan_id}"
                ),
                plan_id=plan.plan_id,
                source_node_id=
                    plan.source_node_id,
                status=SimulationStatus.RUNNING,
                started_at=started_at,
                dry_run=True,
                approval_granted=
                    self.approval_granted,
                metadata={
                    "execution_enabled": False,
                    "automatic_execution_allowed":
                        plan
                        .automatic_execution_allowed,
                },
            )
        )

        outcomes: dict[
            str,
            SimulatedStepOutcome,
        ] = {}

        for step in plan.steps:
            step_result = (
                self._simulate_step(
                    step,
                    outcomes,
                )
            )

            simulation.steps.append(
                step_result
            )

            outcomes[step.step_id] = (
                step_result.outcome
            )

            if (
                step_result.outcome
                == SimulatedStepOutcome.FAILED
            ):
                simulation.failure_step_id = (
                    step.step_id
                )
                break

        failed = any(
            step.outcome
            == SimulatedStepOutcome.FAILED
            for step in simulation.steps
        )

        blocked = any(
            step.outcome
            == SimulatedStepOutcome.BLOCKED
            for step in simulation.steps
        )

        if failed:
            self._rollback(
                plan,
                simulation,
            )

            simulation.status = (
                SimulationStatus.ROLLED_BACK
                if simulation.rollback_performed
                else SimulationStatus.FAILED
            )

            simulation.summary = (
                "Simulation failed and rollback "
                "was evaluated."
            )

        elif blocked:
            simulation.status = (
                SimulationStatus.BLOCKED
            )

            simulation.summary = (
                "Simulation stopped at an "
                "approval or dependency gate."
            )

        else:
            simulation.status = (
                SimulationStatus.COMPLETED
            )

            simulation.summary = (
                "All execution-plan steps were "
                "simulated successfully."
            )

        simulation.completed_at = datetime.now(
            timezone.utc
        )

        return simulation


def simulate_execution_plan(
    plan: ExecutionPlan,
    *,
    approval_granted: bool = False,
    fail_step_ids: (
        Iterable[str] | None
    ) = None,
) -> ExecutionSimulationResult:
    return ExecutionSimulator(
        approval_granted=
            approval_granted,
        fail_step_ids=
            fail_step_ids,
    ).simulate(plan)
