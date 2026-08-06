from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.models.decision_action import (
    DecisionAction,
    DecisionActionStatus,
)
from app.models.execution_authorization import (
    AuthorizationStatus,
    ExecutionAuthorization,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.models.execution_simulation import (
    ExecutionSimulationResult,
    SimulationStatus,
)
from app.services.decision_action_service import (
    DecisionActionConflict,
    DecisionActionService,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_simulator import (
    simulate_execution_plan,
)


class SafeDecisionExecutionBridgeError(RuntimeError):
    """Base error for safe decision execution bridge."""


class SafeDecisionExecutionBindingError(
    SafeDecisionExecutionBridgeError
):
    """Raised when action, plan and authorization do not match."""


class SafeDecisionExecutionNotFound(
    SafeDecisionExecutionBridgeError
):
    """Raised when action or authorization cannot be found."""


class SafeDecisionExecutionNotAllowed(
    SafeDecisionExecutionBridgeError
):
    """Raised when execution is not authorized or safe."""


@dataclass(slots=True)
class SafeDecisionExecutionResult:
    action: DecisionAction
    authorization: ExecutionAuthorization
    simulation: ExecutionSimulationResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "authorization": (
                self.authorization.to_dict()
            ),
            "simulation": (
                self.simulation.to_dict()
            ),
            "safety": {
                "dry_run_only": True,
                "network_io_performed": False,
                "device_command_executed": False,
            },
        }


class SafeDecisionExecutionBridge:
    """
    Safely coordinates an approved DecisionAction with the
    dry-run execution simulator.

    This bridge never contacts managed devices and never executes
    network commands. Only DRY_RUN_ONLY execution plans are accepted.
    """

    def __init__(
        self,
        *,
        action_service: DecisionActionService,
        authorization_store: ExecutionAuthorizationStore,
    ) -> None:
        if not isinstance(
            action_service,
            DecisionActionService,
        ):
            raise TypeError(
                "action_service must be a "
                "DecisionActionService"
            )

        if not isinstance(
            authorization_store,
            ExecutionAuthorizationStore,
        ):
            raise TypeError(
                "authorization_store must be an "
                "ExecutionAuthorizationStore"
            )

        self.action_service = action_service
        self.authorization_store = (
            authorization_store
        )

    @staticmethod
    def _validate_bindings(
        *,
        action: DecisionAction,
        authorization: ExecutionAuthorization,
        plan: ExecutionPlan,
    ) -> None:
        if (
            action.decision_id
            != authorization.decision_id
        ):
            raise SafeDecisionExecutionBindingError(
                "Authorization decision_id does not match "
                "DecisionAction decision_id"
            )

        if (
            plan.decision_id
            != action.decision_id
        ):
            raise SafeDecisionExecutionBindingError(
                "Execution plan decision_id does not match "
                "DecisionAction decision_id"
            )

        if (
            plan.plan_id
            != authorization.plan_id
        ):
            raise SafeDecisionExecutionBindingError(
                "Execution plan plan_id does not match "
                "authorization plan_id"
            )

        if (
            plan.source_node_id
            != authorization.source_node_id
        ):
            raise SafeDecisionExecutionBindingError(
                "Execution plan source_node_id does not match "
                "authorization source_node_id"
            )

    @staticmethod
    def _validate_execution_safety(
        *,
        action: DecisionAction,
        authorization: ExecutionAuthorization,
        plan: ExecutionPlan,
    ) -> None:
        if (
            action.status
            is not DecisionActionStatus.APPROVED
        ):
            raise SafeDecisionExecutionNotAllowed(
                "Decision action must be approved "
                "before simulation"
            )

        if (
            authorization.status
            is not AuthorizationStatus.APPROVED
        ):
            raise SafeDecisionExecutionNotAllowed(
                "Execution authorization must be approved"
            )

        if not authorization.is_usable:
            raise SafeDecisionExecutionNotAllowed(
                "Execution authorization is not usable"
            )

        if not plan.dry_run_only:
            raise SafeDecisionExecutionNotAllowed(
                "Only dry-run execution plans are allowed"
            )

        if plan.automatic_execution_allowed:
            raise SafeDecisionExecutionNotAllowed(
                "Automatic device execution is not allowed "
                "by this bridge"
            )

    def execute(
        self,
        *,
        decision_id: str,
        authorization_id: str,
        plan: ExecutionPlan,
        fail_step_ids: Iterable[str] | None = None,
    ) -> SafeDecisionExecutionResult:
        action = self.action_service.get_action(
            decision_id
        )

        authorization = (
            self.authorization_store.get(
                authorization_id
            )
        )

        if authorization is None:
            raise SafeDecisionExecutionNotFound(
                "Execution authorization not found: "
                f"{authorization_id}"
            )

        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan must be an ExecutionPlan"
            )

        self._validate_bindings(
            action=action,
            authorization=authorization,
            plan=plan,
        )

        self._validate_execution_safety(
            action=action,
            authorization=authorization,
            plan=plan,
        )

        executing_action = (
            self.action_service.mark_executing(
                action.decision_id
            )
        )

        consumed_authorization = (
            self.authorization_store.consume(
                authorization.authorization_id
            )
        )

        try:
            simulation = simulate_execution_plan(
                plan,
                approval_granted=True,
                fail_step_ids=fail_step_ids,
            )
        except Exception as exc:
            failed_action = (
                self.action_service.mark_failed(
                    executing_action.decision_id,
                    error=(
                        "Execution simulation raised "
                        f"{type(exc).__name__}: {exc}"
                    ),
                )
            )

            raise SafeDecisionExecutionBridgeError(
                "Dry-run execution simulation failed"
            ) from exc

        simulation_payload = simulation.to_dict()

        if (
            simulation.status
            is SimulationStatus.COMPLETED
        ):
            final_action = (
                self.action_service.mark_completed(
                    executing_action.decision_id,
                    result={
                        "simulation":
                            simulation_payload,
                        "authorization_id":
                            consumed_authorization
                            .authorization_id,
                        "dry_run": True,
                        "network_io_performed": False,
                        "device_command_executed": False,
                    },
                )
            )
        else:
            final_action = (
                self.action_service.mark_failed(
                    executing_action.decision_id,
                    error=(
                        "Dry-run simulation ended with "
                        f"status '{simulation.status.value}'"
                    ),
                )
            )

        return SafeDecisionExecutionResult(
            action=final_action,
            authorization=consumed_authorization,
            simulation=simulation,
        )
