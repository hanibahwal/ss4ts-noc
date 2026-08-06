from __future__ import annotations

import pytest

from app.models.decision_action import (
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionTarget,
)
from app.services.decision_action_service import (
    DecisionActionService,
)
from app.services.decision_execution_runtime import (
    DecisionExecutionRuntime,
    DecisionExecutionRuntimeConflict,
    DecisionExecutionRuntimeNotFound,
)
from tests.test_execution_simulator import (
    make_plan,
)


def make_action(
    service: DecisionActionService,
):
    return service.create_action(
        incident_id="incident:runtime-001",
        problem="Primary link instability",
        recommendation=(
            "Simulate backup-link failover"
        ),
        confidence_percent=96,
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
            site_id="site:riyadh",
            device_id="device:router-01",
        ),
        command=DecisionActionCommand(
            action_type="disable_interface",
            parameters={
                "interface": "ether1",
            },
            rollback_action_type=(
                "enable_interface"
            ),
            rollback_parameters={
                "interface": "ether1",
            },
            verification_steps=(
                "verify_backup_link",
            ),
        ),
        requested_by="runtime-test",
    )


def prepare_runtime(
    tmp_path,
):
    database = (
        tmp_path
        / "decision-execution-runtime.db"
    )

    runtime = DecisionExecutionRuntime(
        database
    )

    action = make_action(
        runtime.action_service
    )

    plan = make_plan()
    plan.decision_id = action.decision_id

    return (
        database,
        runtime,
        action,
        plan,
    )


def test_register_and_get(
    tmp_path,
) -> None:
    (
        _,
        runtime,
        action,
        plan,
    ) = prepare_runtime(
        tmp_path
    )

    created = runtime.register(
        action=action,
        plan=plan,
        authorization_id=(
            "authorization:runtime-001"
        ),
    )

    loaded = runtime.get(
        created.authorization_id
    )

    assert (
        loaded.action.decision_id
        == action.decision_id
    )

    assert (
        loaded.plan.plan_id
        == plan.plan_id
    )

    assert runtime.count() == 1


def test_survives_runtime_restart(
    tmp_path,
) -> None:
    (
        database,
        first_runtime,
        action,
        plan,
    ) = prepare_runtime(
        tmp_path
    )

    first_runtime.register(
        action=action,
        plan=plan,
        authorization_id=(
            "authorization:restart"
        ),
    )

    second_runtime = (
        DecisionExecutionRuntime(
            database
        )
    )

    assert (
        second_runtime.action_service
        .list_actions()
        == []
    )

    loaded = second_runtime.get(
        "authorization:restart"
    )

    assert (
        loaded.action.decision_id
        == action.decision_id
    )

    assert (
        second_runtime.action_service
        .get_action(
            action.decision_id
        )
        .decision_id
        == action.decision_id
    )


def test_update_persists_action_status(
    tmp_path,
) -> None:
    (
        database,
        runtime,
        action,
        plan,
    ) = prepare_runtime(
        tmp_path
    )

    authorization_id = (
        "authorization:update"
    )

    runtime.register(
        action=action,
        plan=plan,
        authorization_id=
            authorization_id,
    )

    approved = (
        runtime.action_service.approve(
            action.decision_id,
            approved_by="user:senior",
        )
    )

    runtime.update(
        action=approved,
        plan=plan,
        authorization_id=
            authorization_id,
    )

    restarted = DecisionExecutionRuntime(
        database
    )

    loaded = restarted.get(
        authorization_id
    )

    assert (
        loaded.action.status.value
        == "approved"
    )


def test_duplicate_registration_rejected(
    tmp_path,
) -> None:
    (
        _,
        runtime,
        action,
        plan,
    ) = prepare_runtime(
        tmp_path
    )

    runtime.register(
        action=action,
        plan=plan,
        authorization_id=(
            "authorization:duplicate"
        ),
    )

    with pytest.raises(
        DecisionExecutionRuntimeConflict
    ):
        runtime.register(
            action=action,
            plan=plan,
            authorization_id=(
                "authorization:duplicate"
            ),
        )


def test_remove_and_missing(
    tmp_path,
) -> None:
    (
        _,
        runtime,
        action,
        plan,
    ) = prepare_runtime(
        tmp_path
    )

    authorization_id = (
        "authorization:remove"
    )

    runtime.register(
        action=action,
        plan=plan,
        authorization_id=
            authorization_id,
    )

    assert (
        runtime.remove(
            authorization_id
        )
        is True
    )

    assert runtime.count() == 0

    with pytest.raises(
        DecisionExecutionRuntimeNotFound
    ):
        runtime.get(
            authorization_id
        )


def test_clear(
    tmp_path,
) -> None:
    (
        _,
        runtime,
        action,
        plan,
    ) = prepare_runtime(
        tmp_path
    )

    runtime.register(
        action=action,
        plan=plan,
        authorization_id=(
            "authorization:clear"
        ),
    )

    assert runtime.clear() == 1
    assert runtime.count() == 0
