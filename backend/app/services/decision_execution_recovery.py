from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.decision_action import (
    DecisionActionStatus,
)
from app.models.execution_recovery import (
    ExecutionRecovery,
    RecoveryStatus,
)
from app.services.decision_execution_runtime import (
    DecisionExecutionRuntime,
    DecisionExecutionRuntimeNotFound,
    runtime,
)


@dataclass(slots=True)
class DecisionExecutionRecoveryResult:
    authorization_id: str
    decision_id: str | None
    reconciled: bool
    previous_status: str | None
    current_status: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization_id":
                self.authorization_id,
            "decision_id":
                self.decision_id,
            "reconciled":
                self.reconciled,
            "previous_status":
                self.previous_status,
            "current_status":
                self.current_status,
            "reason":
                self.reason,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        }


class DecisionExecutionRecoveryReconciler:
    """
    Reconcile recovered workers with persistent DecisionAction state.

    Lease and heartbeat recovery is completed first in the authorization
    database. This reconciler then repairs a corresponding DecisionAction
    that remained in EXECUTING after a worker crash or timeout.

    It never contacts managed devices and never executes commands.
    """

    def __init__(
        self,
        decision_runtime: (
            DecisionExecutionRuntime
        ) = runtime,
    ) -> None:
        if not isinstance(
            decision_runtime,
            DecisionExecutionRuntime,
        ):
            raise TypeError(
                "decision_runtime must be a "
                "DecisionExecutionRuntime"
            )

        self.decision_runtime = (
            decision_runtime
        )

    def reconcile(
        self,
        recovery: ExecutionRecovery,
    ) -> DecisionExecutionRecoveryResult:
        if not isinstance(
            recovery,
            ExecutionRecovery,
        ):
            raise TypeError(
                "recovery must be an "
                "ExecutionRecovery"
            )

        if (
            recovery.status
            is not RecoveryStatus.RECOVERED
        ):
            return DecisionExecutionRecoveryResult(
                authorization_id=(
                    recovery.authorization_id
                ),
                decision_id=None,
                reconciled=False,
                previous_status=None,
                current_status=None,
                reason=(
                    "recovery_not_successful"
                ),
            )

        try:
            item = self.decision_runtime.get(
                recovery.authorization_id
            )
        except DecisionExecutionRuntimeNotFound:
            return DecisionExecutionRecoveryResult(
                authorization_id=(
                    recovery.authorization_id
                ),
                decision_id=None,
                reconciled=False,
                previous_status=None,
                current_status=None,
                reason=(
                    "decision_runtime_not_found"
                ),
            )

        previous_status = (
            item.action.status
        )

        if (
            previous_status
            is not DecisionActionStatus.EXECUTING
        ):
            return DecisionExecutionRecoveryResult(
                authorization_id=(
                    recovery.authorization_id
                ),
                decision_id=(
                    item.action.decision_id
                ),
                reconciled=False,
                previous_status=(
                    previous_status.value
                ),
                current_status=(
                    previous_status.value
                ),
                reason=(
                    "decision_action_not_executing"
                ),
            )

        failure_message = (
            "Execution worker recovery detected "
            "an interrupted decision execution: "
            f"worker_id={recovery.worker_id}, "
            f"lease_id={recovery.lease_id}, "
            f"recovery_id={recovery.recovery_id}, "
            f"reason={recovery.reason.value}, "
            f"decision={recovery.decision.value}"
        )

        failed_action = (
            self.decision_runtime
            .action_service
            .mark_failed(
                item.action.decision_id,
                error=failure_message,
            )
        )

        self.decision_runtime.update(
            action=failed_action,
            plan=item.plan,
            authorization_id=(
                recovery.authorization_id
            ),
        )

        return DecisionExecutionRecoveryResult(
            authorization_id=(
                recovery.authorization_id
            ),
            decision_id=(
                failed_action.decision_id
            ),
            reconciled=True,
            previous_status=(
                previous_status.value
            ),
            current_status=(
                failed_action.status.value
            ),
            reason=(
                "interrupted_execution_marked_failed"
            ),
        )


def reconcile_decision_execution_recovery(
    recovery: ExecutionRecovery,
) -> DecisionExecutionRecoveryResult:
    return (
        DecisionExecutionRecoveryReconciler()
        .reconcile(
            recovery
        )
    )
