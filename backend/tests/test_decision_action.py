import pytest

from app.models.decision_action import (
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionStatus,
    DecisionActionTarget,
)
from app.services.decision_action_service import (
    DecisionActionConflict,
    DecisionActionNotFound,
    DecisionActionService,
)


def make_target() -> DecisionActionTarget:
    return DecisionActionTarget(
        router_ip="192.168.88.1",
        interface_name="ether1",
        site_id="site:riyadh",
        device_id="device:router-01",
    )


def make_reversible_command() -> DecisionActionCommand:
    return DecisionActionCommand(
        action_type="disable_interface",
        parameters={
            "interface": "ether1",
        },
        rollback_action_type="enable_interface",
        rollback_parameters={
            "interface": "ether1",
        },
        verification_steps=(
            "verify_interface_disabled",
            "verify_backup_link_active",
        ),
    )


def make_read_only_command() -> DecisionActionCommand:
    return DecisionActionCommand(
        action_type="inspect_interface",
        parameters={
            "interface": "ether1",
        },
        verification_steps=(
            "collect_interface_status",
        ),
    )


def test_low_risk_read_only_action_is_approved() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:001",
        problem="Interface packet loss",
        recommendation="Inspect interface status",
        confidence_percent=95,
        risk_level=DecisionActionRiskLevel.LOW,
        execution_mode=(
            DecisionActionExecutionMode.READ_ONLY
        ),
        target=make_target(),
        command=make_read_only_command(),
        requested_by="decision-engine",
    )

    assert action.status is DecisionActionStatus.APPROVED
    assert action.approval_required is False


def test_high_risk_action_requires_approval() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:002",
        problem="Primary interface instability",
        recommendation="Disable primary interface",
        confidence_percent=93,
        risk_level=DecisionActionRiskLevel.HIGH,
        execution_mode=(
            DecisionActionExecutionMode.APPROVAL_REQUIRED
        ),
        target=make_target(),
        command=make_reversible_command(),
        requested_by="decision-engine",
    )

    assert (
        action.status
        is DecisionActionStatus.PENDING_APPROVAL
    )
    assert action.approval_required is True


def test_high_risk_action_without_rollback_rejected() -> None:
    service = DecisionActionService()

    with pytest.raises(
        ValueError,
        match="must define rollback",
    ):
        service.create_action(
            incident_id="incident:003",
            problem="Interface instability",
            recommendation="Disable interface",
            confidence_percent=90,
            risk_level=DecisionActionRiskLevel.HIGH,
            execution_mode=(
                DecisionActionExecutionMode
                .APPROVAL_REQUIRED
            ),
            target=make_target(),
            command=DecisionActionCommand(
                action_type="disable_interface",
            ),
            requested_by="decision-engine",
        )


def test_automatic_action_must_be_low_risk() -> None:
    service = DecisionActionService()

    with pytest.raises(
        ValueError,
        match="Only low-risk actions",
    ):
        service.create_action(
            incident_id="incident:004",
            problem="Routing instability",
            recommendation="Restart routing process",
            confidence_percent=80,
            risk_level=DecisionActionRiskLevel.MEDIUM,
            execution_mode=(
                DecisionActionExecutionMode.AUTOMATIC
            ),
            target=make_target(),
            command=make_reversible_command(),
            requested_by="decision-engine",
            approval_required=False,
        )


def test_pending_action_can_be_approved() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:005",
        problem="Primary interface failure",
        recommendation="Disable primary interface",
        confidence_percent=98,
        risk_level=DecisionActionRiskLevel.HIGH,
        execution_mode=(
            DecisionActionExecutionMode.APPROVAL_REQUIRED
        ),
        target=make_target(),
        command=make_reversible_command(),
        requested_by="decision-engine",
    )

    approved = service.approve(
        action.decision_id,
        approved_by="hani",
    )

    assert approved.status is DecisionActionStatus.APPROVED
    assert approved.metadata["approved_by"] == "hani"
    assert "approved_at" in approved.metadata


def test_approved_action_can_enter_execution() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:006",
        problem="Packet loss",
        recommendation="Inspect interface",
        confidence_percent=99,
        risk_level=DecisionActionRiskLevel.LOW,
        execution_mode=(
            DecisionActionExecutionMode.READ_ONLY
        ),
        target=make_target(),
        command=make_read_only_command(),
        requested_by="decision-engine",
    )

    executing = service.mark_executing(
        action.decision_id
    )

    assert (
        executing.status
        is DecisionActionStatus.EXECUTING
    )


def test_execution_can_be_completed() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:007",
        problem="Interface health check",
        recommendation="Inspect interface",
        confidence_percent=99,
        risk_level=DecisionActionRiskLevel.LOW,
        execution_mode=(
            DecisionActionExecutionMode.READ_ONLY
        ),
        target=make_target(),
        command=make_read_only_command(),
        requested_by="decision-engine",
    )

    service.mark_executing(
        action.decision_id
    )

    completed = service.mark_completed(
        action.decision_id,
        result={
            "interface_running": True,
            "packet_loss_percent": 0,
        },
    )

    assert (
        completed.status
        is DecisionActionStatus.COMPLETED
    )

    assert (
        completed.metadata["execution_result"]
        ["interface_running"]
        is True
    )


def test_unapproved_action_cannot_execute() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:008",
        problem="Primary link instability",
        recommendation="Disable primary interface",
        confidence_percent=92,
        risk_level=DecisionActionRiskLevel.HIGH,
        execution_mode=(
            DecisionActionExecutionMode.APPROVAL_REQUIRED
        ),
        target=make_target(),
        command=make_reversible_command(),
        requested_by="decision-engine",
    )

    with pytest.raises(
        DecisionActionConflict,
        match="Only approved actions",
    ):
        service.mark_executing(
            action.decision_id
        )


def test_action_can_be_rejected() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:009",
        problem="Primary link instability",
        recommendation="Disable interface",
        confidence_percent=85,
        risk_level=DecisionActionRiskLevel.HIGH,
        execution_mode=(
            DecisionActionExecutionMode.APPROVAL_REQUIRED
        ),
        target=make_target(),
        command=make_reversible_command(),
        requested_by="decision-engine",
    )

    rejected = service.reject(
        action.decision_id,
        rejected_by="network-engineer",
        reason="Maintenance window is not active",
    )

    assert rejected.status is DecisionActionStatus.REJECTED

    assert (
        rejected.metadata["rejection_reason"]
        == "Maintenance window is not active"
    )


def test_unknown_action_raises_not_found() -> None:
    service = DecisionActionService()

    with pytest.raises(
        DecisionActionNotFound,
        match="Decision action not found",
    ):
        service.get_action(
            "decision:missing"
        )


def test_list_actions_filters_status() -> None:
    service = DecisionActionService()

    service.create_action(
        incident_id="incident:010",
        problem="Interface inspection",
        recommendation="Inspect interface",
        confidence_percent=99,
        risk_level=DecisionActionRiskLevel.LOW,
        execution_mode=(
            DecisionActionExecutionMode.READ_ONLY
        ),
        target=make_target(),
        command=make_read_only_command(),
        requested_by="decision-engine",
    )

    service.create_action(
        incident_id="incident:011",
        problem="Primary link failure",
        recommendation="Disable interface",
        confidence_percent=95,
        risk_level=DecisionActionRiskLevel.HIGH,
        execution_mode=(
            DecisionActionExecutionMode.APPROVAL_REQUIRED
        ),
        target=make_target(),
        command=make_reversible_command(),
        requested_by="decision-engine",
    )

    pending = service.list_actions(
        status=(
            DecisionActionStatus.PENDING_APPROVAL
        )
    )

    assert len(pending) == 1
    assert (
        pending[0].status
        is DecisionActionStatus.PENDING_APPROVAL
    )


def test_decision_serializes() -> None:
    service = DecisionActionService()

    action = service.create_action(
        incident_id="incident:012",
        problem="Interface packet loss",
        recommendation="Inspect interface",
        confidence_percent=91,
        risk_level=DecisionActionRiskLevel.LOW,
        execution_mode=(
            DecisionActionExecutionMode.READ_ONLY
        ),
        target=make_target(),
        command=make_read_only_command(),
        requested_by="decision-engine",
        metadata={
            "source": "root-cause-analysis",
        },
    )

    payload = action.to_dict()

    assert payload["decision_id"].startswith(
        "decision:"
    )

    assert payload["risk_level"] == "low"
    assert payload["execution_mode"] == "read_only"
    assert payload["status"] == "approved"

    assert (
        payload["target"]["router_ip"]
        == "192.168.88.1"
    )
