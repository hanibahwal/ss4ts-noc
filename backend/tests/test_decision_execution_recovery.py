from __future__ import annotations

from dataclasses import replace
from datetime import (
    datetime,
    timezone,
)

from app.models.decision_action import (
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionStatus,
    DecisionActionTarget,
)
from app.models.execution_recovery import (
    ExecutionRecovery,
    RecoveryDecision,
    RecoveryReason,
    RecoveryStatus,
)
from app.services.decision_execution_recovery import (
    DecisionExecutionRecoveryReconciler,
)
from app.services.decision_execution_runtime import (
    DecisionExecutionRuntime,
)
from tests.test_execution_simulator import (
    make_plan,
)


def make_recovery(
    authorization_id: str,
    *,
    status: RecoveryStatus = (
        RecoveryStatus.RECOVERED
    ),
) -> ExecutionRecovery:
    now = datetime.now(
        timezone.utc
    )

    return ExecutionRecovery(
        recovery_id="recovery:decision-001",
        worker_id="worker:decision-001",
        lease_id="lease:decision-001",
        authorization_id=authorization_id,
        status=status,
        decision=(
            RecoveryDecision.REVOKE_LEASE
            if status
            is RecoveryStatus.RECOVERED
            else RecoveryDecision.NO_ACTION
        ),
        reason=(
            RecoveryReason.WORKER_STALE
            if status
            is RecoveryStatus.RECOVERED
            else RecoveryReason
            .LEASE_NOT_ACTIVE
        ),
        detected_at=now,
        completed_at=now,
        previous_lease_version=1,
        current_lease_version=2,
        previous_heartbeat_version=1,
        current_heartbeat_version=2,
    )


def make_runtime_item(
    tmp_path,
    *,
    status: DecisionActionStatus,
):
    decision_runtime = (
        DecisionExecutionRuntime(
            tmp_path
            / "decision-runtime.db"
        )
    )

    action = (
        decision_runtime
        .action_service
        .create_action(
            incident_id=(
                "incident:recovery-001"
            ),
            problem=(
                "Interrupted decision execution"
            ),
            recommendation=(
                "Reconcile execution state"
            ),
            confidence_percent=98,
            risk_level=(
                DecisionActionRiskLevel.HIGH
            ),
            execution_mode=(
                DecisionActionExecutionMode
                .APPROVAL_REQUIRED
            ),
            target=DecisionActionTarget(
                router_ip="192.168.88.1",
                interface_name="ether1",
            ),
            command=DecisionActionCommand(
                action_type=(
                    "disable_interface"
                ),
                parameters={
                    "interface": "ether1",
                },
                rollback_action_type=(
                    "enable_interface"
                ),
                rollback_parameters={
                    "interface": "ether1",
                },
            ),
            requested_by=(
                "decision-recovery-test"
            ),
        )
    )

    action = replace(
        action,
        status=status,
    )

    decision_runtime.action_service._actions[
        action.decision_id
    ] = action

    plan = make_plan()
    plan.decision_id = action.decision_id

    authorization_id = (
        "authorization:decision-recovery"
    )

    decision_runtime.register(
        action=action,
        plan=plan,
        authorization_id=
            authorization_id,
    )

    return (
        decision_runtime,
        authorization_id,
        action,
    )


def test_recovered_worker_marks_executing_action_failed(
    tmp_path,
) -> None:
    (
        decision_runtime,
        authorization_id,
        action,
    ) = make_runtime_item(
        tmp_path,
        status=(
            DecisionActionStatus.EXECUTING
        ),
    )

    reconciler = (
        DecisionExecutionRecoveryReconciler(
            decision_runtime
        )
    )

    result = reconciler.reconcile(
        make_recovery(
            authorization_id
        )
    )

    assert result.reconciled is True

    assert (
        result.previous_status
        == "executing"
    )

    assert result.current_status == "failed"

    restarted = DecisionExecutionRuntime(
        decision_runtime.database_path
    )

    loaded = restarted.get(
        authorization_id
    )

    assert (
        loaded.action.status
        is DecisionActionStatus.FAILED
    )

    assert (
        "worker:decision-001"
        in loaded.action.metadata[
            "execution_error"
        ]
    )

    assert (
        loaded.action.decision_id
        == action.decision_id
    )


def test_completed_action_is_not_changed(
    tmp_path,
) -> None:
    (
        decision_runtime,
        authorization_id,
        _,
    ) = make_runtime_item(
        tmp_path,
        status=(
            DecisionActionStatus.COMPLETED
        ),
    )

    result = (
        DecisionExecutionRecoveryReconciler(
            decision_runtime
        )
        .reconcile(
            make_recovery(
                authorization_id
            )
        )
    )

    assert result.reconciled is False

    assert (
        result.reason
        == "decision_action_not_executing"
    )

    assert result.current_status == "completed"


def test_skipped_recovery_does_not_change_action(
    tmp_path,
) -> None:
    (
        decision_runtime,
        authorization_id,
        _,
    ) = make_runtime_item(
        tmp_path,
        status=(
            DecisionActionStatus.EXECUTING
        ),
    )

    result = (
        DecisionExecutionRecoveryReconciler(
            decision_runtime
        )
        .reconcile(
            make_recovery(
                authorization_id,
                status=RecoveryStatus.SKIPPED,
            )
        )
    )

    assert result.reconciled is False

    assert (
        result.reason
        == "recovery_not_successful"
    )

    loaded = decision_runtime.get(
        authorization_id
    )

    assert (
        loaded.action.status
        is DecisionActionStatus.EXECUTING
    )


def test_missing_runtime_is_safe(
    tmp_path,
) -> None:
    decision_runtime = (
        DecisionExecutionRuntime(
            tmp_path
            / "missing-runtime.db"
        )
    )

    result = (
        DecisionExecutionRecoveryReconciler(
            decision_runtime
        )
        .reconcile(
            make_recovery(
                "authorization:missing"
            )
        )
    )

    assert result.reconciled is False

    assert (
        result.reason
        == "decision_runtime_not_found"
    )


def test_reconciliation_is_idempotent(
    tmp_path,
) -> None:
    (
        decision_runtime,
        authorization_id,
        _,
    ) = make_runtime_item(
        tmp_path,
        status=(
            DecisionActionStatus.EXECUTING
        ),
    )

    reconciler = (
        DecisionExecutionRecoveryReconciler(
            decision_runtime
        )
    )

    recovery = make_recovery(
        authorization_id
    )

    first = reconciler.reconcile(
        recovery
    )

    second = reconciler.reconcile(
        recovery
    )

    assert first.reconciled is True
    assert second.reconciled is False

    assert (
        second.reason
        == "decision_action_not_executing"
    )

    assert second.current_status == "failed"
