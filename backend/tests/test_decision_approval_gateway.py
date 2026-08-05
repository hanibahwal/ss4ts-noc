from __future__ import annotations

import pytest

from app.models.decision_action import (
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionStatus,
    DecisionActionTarget,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationStatus,
)
from app.models.execution_concurrency import (
    AuthorizationVersionConflict,
    IdempotencyDisposition,
)
from app.services.decision_action_service import (
    DecisionActionService,
)
from app.services.decision_approval_gateway import (
    DecisionApprovalBindingError,
    DecisionApprovalGateway,
    DecisionApprovalNotFound,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
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


def senior() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:senior",
        display_name="Senior Engineer",
        role=ApprovalRole.SENIOR_ENGINEER,
    )


def engineer() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:engineer",
        display_name="Network Engineer",
        role=ApprovalRole.NETWORK_ENGINEER,
    )


def make_gateway(
    tmp_path,
) -> tuple[
    DecisionApprovalGateway,
    DecisionActionService,
    ExecutionAuthorizationStore,
]:
    action_service = DecisionActionService()

    authorization_store = (
        ExecutionAuthorizationStore(
            tmp_path
            / "decision-approval-gateway.db"
        )
    )

    gateway = DecisionApprovalGateway(
        action_service=action_service,
        authorization_store=authorization_store,
    )

    return (
        gateway,
        action_service,
        authorization_store,
    )


def make_target() -> DecisionActionTarget:
    return DecisionActionTarget(
        router_ip="192.168.88.1",
        interface_name="ether1",
        site_id="site:riyadh",
        device_id="device:router-01",
    )


def make_command() -> DecisionActionCommand:
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


def create_pending_action(
    service: DecisionActionService,
):
    return service.create_action(
        incident_id="incident:gateway-001",
        problem="Primary interface instability",
        recommendation=(
            "Disable primary interface "
            "and verify backup connectivity"
        ),
        confidence_percent=95,
        risk_level=DecisionActionRiskLevel.HIGH,
        execution_mode=(
            DecisionActionExecutionMode
            .APPROVAL_REQUIRED
        ),
        target=make_target(),
        command=make_command(),
        requested_by="decision-engine",
    )


def build_matching_plan(
    decision_id: str,
):
    plan = make_plan()
    plan.decision_id = decision_id

    return plan


def test_gateway_creates_authorization(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        authorization_store,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    plan = build_matching_plan(
        action.decision_id
    )

    result = gateway.request_authorization(
        action=action,
        plan=plan,
        requester=requester(),
    )

    assert (
        result.action.decision_id
        == action.decision_id
    )

    assert (
        result.authorization.decision_id
        == action.decision_id
    )

    assert (
        result.authorization.status
        == AuthorizationStatus.PENDING
    )

    assert (
        result.action.status
        == DecisionActionStatus.PENDING_APPROVAL
    )

    assert (
        authorization_store.get(
            result.authorization.authorization_id
        )
        is not None
    )


def test_gateway_preserves_safety_metadata(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        _,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    result = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    metadata = (
        result.authorization.metadata
    )

    assert (
        metadata["decision_action_id"]
        == action.decision_id
    )

    assert (
        metadata["network_io_performed"]
        is False
    )

    assert (
        metadata["device_command_executed"]
        is False
    )

    assert (
        metadata["gateway"]
        == "decision_approval_gateway"
    )


def test_mismatched_decision_id_rejected(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        _,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    plan = make_plan()
    plan.decision_id = "decision:different"

    with pytest.raises(
        DecisionApprovalBindingError,
        match="does not match",
    ):
        gateway.request_authorization(
            action=action,
            plan=plan,
            requester=requester(),
        )


def test_pending_authorization_can_be_approved(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        authorization_store,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    request = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    version = (
        authorization_store
        .get_record_version(
            request.authorization
            .authorization_id
        )
    )

    result = gateway.approve(
        request.authorization.authorization_id,
        approver=senior(),
        expected_version=version,
        idempotency_key=(
            "decision-approval-001"
        ),
    )

    assert (
        result.authorization.status
        == AuthorizationStatus.APPROVED
    )

    assert (
        result.authorization.execution_allowed
        is True
    )

    assert (
        result.action.status
        == DecisionActionStatus.APPROVED
    )

    assert result.mutation is not None

    assert (
        result.mutation.disposition
        == IdempotencyDisposition.NEW
    )


def test_same_approval_is_replayed(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        authorization_store,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    request = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    authorization_id = (
        request.authorization.authorization_id
    )

    version = (
        authorization_store
        .get_record_version(
            authorization_id
        )
    )

    first = gateway.approve(
        authorization_id,
        approver=senior(),
        expected_version=version,
        idempotency_key=(
            "decision-approval-replay-001"
        ),
    )

    replay = gateway.approve(
        authorization_id,
        approver=senior(),
        expected_version=version,
        idempotency_key=(
            "decision-approval-replay-001"
        ),
    )

    assert first.mutation is not None
    assert replay.mutation is not None

    assert (
        first.mutation.disposition
        == IdempotencyDisposition.NEW
    )

    assert (
        replay.mutation.disposition
        == IdempotencyDisposition.REPLAY
    )

    assert replay.mutation.replayed is True

    assert (
        replay.action.status
        == DecisionActionStatus.APPROVED
    )


def test_stale_version_is_rejected(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        authorization_store,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    request = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    authorization_id = (
        request.authorization.authorization_id
    )

    gateway.approve(
        authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=(
            "decision-version-first"
        ),
    )

    with pytest.raises(
        AuthorizationVersionConflict,
    ):
        gateway.approve(
            authorization_id,
            approver=senior(),
            expected_version=1,
            idempotency_key=(
                "decision-version-stale"
            ),
        )

    assert (
        authorization_store
        .get_record_version(
            authorization_id
        )
        == 2
    )


def test_insufficient_role_cannot_approve(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        authorization_store,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    request = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    authorization_id = (
        request.authorization.authorization_id
    )

    with pytest.raises(
        PermissionError,
        match="insufficient",
    ):
        gateway.approve(
            authorization_id,
            approver=engineer(),
            expected_version=1,
            idempotency_key=(
                "decision-role-insufficient"
            ),
        )

    loaded_action = (
        action_service.get_action(
            action.decision_id
        )
    )

    assert (
        loaded_action.status
        == DecisionActionStatus.PENDING_APPROVAL
    )

    assert (
        authorization_store
        .get_record_version(
            authorization_id
        )
        == 1
    )


def test_authorization_can_be_rejected(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        _,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    request = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    result = gateway.reject(
        request.authorization.authorization_id,
        approver=senior(),
        reason=(
            "Maintenance window is not active"
        ),
    )

    assert (
        result.authorization.status
        == AuthorizationStatus.REJECTED
    )

    assert (
        result.authorization.execution_allowed
        is False
    )

    assert (
        result.action.status
        == DecisionActionStatus.REJECTED
    )

    assert (
        result.action.metadata[
            "rejection_reason"
        ]
        == "Maintenance window is not active"
    )


def test_unknown_authorization_rejected(
    tmp_path,
) -> None:
    (
        gateway,
        _,
        _,
    ) = make_gateway(tmp_path)

    with pytest.raises(
        DecisionApprovalNotFound,
        match="not found",
    ):
        gateway.get_authorization(
            "authorization:missing"
        )


def test_gateway_records_lifecycle_events(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        authorization_store,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    request = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    authorization_id = (
        request.authorization.authorization_id
    )

    gateway.approve(
        authorization_id,
        approver=senior(),
        expected_version=1,
        idempotency_key=(
            "decision-events-001"
        ),
    )

    events = authorization_store.events(
        authorization_id
    )

    assert [
        event["event_type"]
        for event in events
    ] == [
        "created",
        "approved",
    ]


def test_gateway_result_serializes(
    tmp_path,
) -> None:
    (
        gateway,
        action_service,
        authorization_store,
    ) = make_gateway(tmp_path)

    action = create_pending_action(
        action_service
    )

    request = gateway.request_authorization(
        action=action,
        plan=build_matching_plan(
            action.decision_id
        ),
        requester=requester(),
    )

    result = gateway.approve(
        request.authorization.authorization_id,
        approver=senior(),
        expected_version=(
            authorization_store
            .get_record_version(
                request.authorization
                .authorization_id
            )
        ),
        idempotency_key=(
            "decision-serialize-001"
        ),
    )

    payload = result.to_dict()

    assert (
        payload["action"]["status"]
        == "approved"
    )

    assert (
        payload["authorization"]["status"]
        == "approved"
    )

    assert "mutation" in payload
