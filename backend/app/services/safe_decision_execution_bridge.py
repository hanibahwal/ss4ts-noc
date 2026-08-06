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
from app.models.execution_lease import (
    ExecutionLease,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.models.execution_simulation import (
    ExecutionSimulationResult,
    SimulationStatus,
)
from app.services.decision_action_service import (
    DecisionActionService,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_lease_store import (
    DEFAULT_EXECUTION_LEASE_TTL_SECONDS,
    ExecutionLeaseStore,
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
    """Raised when an action or authorization cannot be found."""


class SafeDecisionExecutionNotAllowed(
    SafeDecisionExecutionBridgeError
):
    """Raised when execution is not authorized or safe."""


@dataclass(slots=True)
class SafeDecisionExecutionResult:
    action: DecisionAction
    authorization: ExecutionAuthorization
    simulation: ExecutionSimulationResult
    lease: ExecutionLease

    @staticmethod
    def _safe_lease_payload(
        lease: ExecutionLease,
    ) -> dict[str, Any]:
        payload = lease.to_dict()

        # Lease tokens are secrets and must never appear
        # in API responses, logs or serialized results.
        payload.pop(
            "lease_token",
            None,
        )

        payload["token_exposed"] = False

        return payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "action":
                self.action.to_dict(),
            "authorization":
                self.authorization.to_dict(),
            "simulation":
                self.simulation.to_dict(),
            "lease":
                self._safe_lease_payload(
                    self.lease
                ),
            "safety": {
                "dry_run_only": True,
                "lease_enforced": True,
                "network_io_performed": False,
                "device_command_executed": False,
            },
        }


class SafeDecisionExecutionBridge:
    """
    Coordinate an approved DecisionAction with the dry-run simulator.

    A persistent execution lease is acquired before authorization
    consumption. The lease prevents two workers from processing the
    same authorization concurrently.

    This bridge never contacts managed devices and never executes
    network commands.
    """

    def __init__(
        self,
        *,
        action_service: DecisionActionService,
        authorization_store: ExecutionAuthorizationStore,
        lease_store: ExecutionLeaseStore | None = None,
        default_lease_ttl_seconds: int = (
            DEFAULT_EXECUTION_LEASE_TTL_SECONDS
        ),
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

        if (
            lease_store is not None
            and not isinstance(
                lease_store,
                ExecutionLeaseStore,
            )
        ):
            raise TypeError(
                "lease_store must be an "
                "ExecutionLeaseStore"
            )

        default_lease_ttl_seconds = int(
            default_lease_ttl_seconds
        )

        if default_lease_ttl_seconds < 5:
            raise ValueError(
                "default_lease_ttl_seconds "
                "must be at least 5"
            )

        if default_lease_ttl_seconds > 3600:
            raise ValueError(
                "default_lease_ttl_seconds "
                "must not exceed 3600"
            )

        self.action_service = action_service
        self.authorization_store = (
            authorization_store
        )

        # The lease store must use the same SQLite database
        # as the execution authorization store.
        self.lease_store = (
            lease_store
            or ExecutionLeaseStore(
                authorization_store.database_path
            )
        )

        if (
            self.lease_store.database_path.resolve()
            != authorization_store.database_path.resolve()
        ):
            raise ValueError(
                "lease_store and authorization_store "
                "must use the same database"
            )

        self.default_lease_ttl_seconds = (
            default_lease_ttl_seconds
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
        owner_id: str = "worker:decision-simulator",
        lease_ttl_seconds: int | None = None,
        fail_step_ids: Iterable[str] | None = None,
    ) -> SafeDecisionExecutionResult:
        normalized_owner_id = str(
            owner_id
        ).strip()

        if not normalized_owner_id:
            raise ValueError(
                "owner_id must not be empty"
            )

        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan must be an ExecutionPlan"
            )

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

        resolved_ttl = (
            self.default_lease_ttl_seconds
            if lease_ttl_seconds is None
            else int(lease_ttl_seconds)
        )

        # Acquisition is atomic and prevents another worker
        # from holding an active lease for this authorization.
        lease = self.lease_store.acquire(
            authorization.authorization_id,
            owner_id=normalized_owner_id,
            ttl_seconds=resolved_ttl,
        )

        released_lease: ExecutionLease | None = None
        simulation: ExecutionSimulationResult | None = None
        final_action: DecisionAction | None = None
        consumed_authorization: (
            ExecutionAuthorization | None
        ) = None

        try:
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
                self.action_service.mark_failed(
                    executing_action.decision_id,
                    error=(
                        "Execution simulation raised "
                        f"{type(exc).__name__}: {exc}"
                    ),
                )

                raise SafeDecisionExecutionBridgeError(
                    "Dry-run execution simulation failed"
                ) from exc

            simulation_payload = (
                simulation.to_dict()
            )

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
                            "lease_id":
                                lease.lease_id,
                            "lease_owner_id":
                                lease.owner_id,
                            "dry_run": True,
                            "network_io_performed":
                                False,
                            "device_command_executed":
                                False,
                        },
                    )
                )
            else:
                final_action = (
                    self.action_service.mark_failed(
                        executing_action.decision_id,
                        error=(
                            "Dry-run simulation ended with "
                            f"status "
                            f"'{simulation.status.value}'"
                        ),
                    )
                )

        finally:
            # Release is attempted for every terminal path.
            # The token remains internal to the bridge.
            current_lease = self.lease_store.get(
                lease.lease_id
            )

            if (
                current_lease is not None
                and current_lease.is_active
            ):
                released_lease = (
                    self.lease_store.release(
                        current_lease.lease_id,
                        lease_token=(
                            current_lease.lease_token
                        ),
                        expected_version=(
                            current_lease.lease_version
                        ),
                    )
                )
            elif current_lease is not None:
                released_lease = current_lease

        if (
            simulation is None
            or final_action is None
            or consumed_authorization is None
            or released_lease is None
        ):
            raise SafeDecisionExecutionBridgeError(
                "Safe decision execution did not "
                "produce a complete result"
            )

        return SafeDecisionExecutionResult(
            action=final_action,
            authorization=consumed_authorization,
            simulation=simulation,
            lease=released_lease,
        )
