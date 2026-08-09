from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
from app.models.execution_simulation import (
    SimulationStatus,
)
from app.services.decision_action_service import (
    DecisionActionService,
)
from app.services.decision_approval_gateway import (
    DecisionApprovalGateway,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_lease_store import (
    ExecutionLeaseStore,
)
from app.services.safe_decision_execution_bridge import (
    SafeDecisionExecutionBindingError,
    SafeDecisionExecutionBridge,
    SafeDecisionExecutionNotAllowed,
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


def make_services(
    tmp_path,
) -> tuple[
    DecisionActionService,
    ExecutionAuthorizationStore,
    DecisionApprovalGateway,
    SafeDecisionExecutionBridge,
]:
    action_service = DecisionActionService()

    authorization_store = (
        ExecutionAuthorizationStore(
            tmp_path
            / "safe-decision-execution.db"
        )
    )

    approval_gateway = DecisionApprovalGateway(
        action_service=action_service,
        authorization_store=authorization_store,
    )

    lease_store = ExecutionLeaseStore(
        authorization_store.database_path
    )

    execution_bridge = (
        SafeDecisionExecutionBridge(
            action_service=action_service,
            authorization_store=(
                authorization_store
            ),
            lease_store=lease_store,
        )
    )

    return (
        action_service,
        authorization_store,
        approval_gateway,
        execution_bridge,
    )


def create_pending_action(
    service: DecisionActionService,
):
    return service.create_action(
        incident_id="incident:safe-execution-001",
        problem="Primary interface instability",
        recommendation=(
            "Simulate disabling the primary "
            "interface and verify backup service"
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


def prepare_approved_execution(
    tmp_path,
):
    (
        action_service,
        authorization_store,
        approval_gateway,
        execution_bridge,
    ) = make_services(tmp_path)

    action = create_pending_action(
        action_service
    )

    plan = make_plan()
    plan.decision_id = action.decision_id

    approval_request = (
        approval_gateway.request_authorization(
            action=action,
            plan=plan,
            requester=requester(),
        )
    )

    authorization_id = (
        approval_request
        .authorization
        .authorization_id
    )

    approval_gateway.approve(
        authorization_id,
        approver=senior(),
        expected_version=(
            authorization_store
            .get_record_version(
                authorization_id
            )
        ),
        idempotency_key=(
            "safe-execution-approval-001"
        ),
    )

    return (
        action_service,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    )


def test_completed_simulation_completes_action(
    tmp_path,
) -> None:
    (
        action_service,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
    )

    assert (
        result.simulation.status
        == SimulationStatus.COMPLETED
    )

    assert (
        result.action.status
        == DecisionActionStatus.COMPLETED
    )

    assert (
        result.authorization.status
        == AuthorizationStatus.USED
    )

    assert result.authorization.consumed is True

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is True

    loaded_action = (
        action_service.get_action(
            action.decision_id
        )
    )

    assert (
        loaded_action.status
        == DecisionActionStatus.COMPLETED
    )


def test_bridge_performs_dry_run_only(
    tmp_path,
) -> None:
    (
        _,
        _,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
    )

    payload = result.to_dict()

    assert payload["safety"] == {
        "dry_run_only": True,
        "lease_enforced": True,
        "network_io_performed": False,
        "device_command_executed": False,
    }

    assert payload["lease"]["status"] == "released"
    assert payload["lease"]["lease_version"] == 2
    assert payload["lease"]["token_exposed"] is False
    assert "lease_token" not in payload["lease"]

    assert result.simulation.dry_run is True

    assert (
        result.simulation.metadata[
            "execution_enabled"
        ]
        is False
    )


def test_authorization_is_consumed_once(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
    )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is True
    assert stored.execution_allowed is False

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="approved|usable",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=authorization_id,
            plan=plan,
        )


def test_unapproved_action_is_blocked(
    tmp_path,
) -> None:
    (
        action_service,
        authorization_store,
        approval_gateway,
        execution_bridge,
    ) = make_services(tmp_path)

    action = create_pending_action(
        action_service
    )

    plan = make_plan()
    plan.decision_id = action.decision_id

    request = (
        approval_gateway.request_authorization(
            action=action,
            plan=plan,
            requester=requester(),
        )
    )

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="action must be approved",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=(
                request.authorization
                .authorization_id
            ),
            plan=plan,
        )

    stored = authorization_store.get(
        request.authorization.authorization_id
    )

    assert stored is not None
    assert stored.consumed is False


def test_pending_authorization_is_blocked(
    tmp_path,
) -> None:
    (
        action_service,
        authorization_store,
        approval_gateway,
        execution_bridge,
    ) = make_services(tmp_path)

    action = create_pending_action(
        action_service
    )

    plan = make_plan()
    plan.decision_id = action.decision_id

    request = (
        approval_gateway.request_authorization(
            action=action,
            plan=plan,
            requester=requester(),
        )
    )

    action_service.approve(
        action.decision_id,
        approved_by="manual:test",
    )

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="authorization must be approved",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=(
                request.authorization
                .authorization_id
            ),
            plan=plan,
        )

    stored = authorization_store.get(
        request.authorization.authorization_id
    )

    assert stored is not None
    assert stored.status == AuthorizationStatus.PENDING
    assert stored.consumed is False


def test_rejected_authorization_is_blocked(
    tmp_path,
) -> None:
    (
        action_service,
        authorization_store,
        approval_gateway,
        execution_bridge,
    ) = make_services(tmp_path)

    action = create_pending_action(
        action_service
    )

    plan = make_plan()
    plan.decision_id = action.decision_id

    request = (
        approval_gateway.request_authorization(
            action=action,
            plan=plan,
            requester=requester(),
        )
    )

    authorization_id = (
        request.authorization
        .authorization_id
    )

    action_service.approve(
        action.decision_id,
        approved_by="manual:test",
    )

    authorization_store.reject(
        authorization_id,
        approver=senior(),
        reason="H32.4 rejection test",
    )

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="authorization must be approved",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=
                authorization_id,
            plan=plan,
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert (
        stored.status
        == AuthorizationStatus.REJECTED
    )
    assert stored.consumed is False
    assert stored.execution_allowed is False


def test_revoked_authorization_is_blocked(
    tmp_path,
) -> None:
    (
        action_service,
        authorization_store,
        approval_gateway,
        execution_bridge,
    ) = make_services(tmp_path)

    action = create_pending_action(
        action_service
    )

    plan = make_plan()
    plan.decision_id = action.decision_id

    request = (
        approval_gateway.request_authorization(
            action=action,
            plan=plan,
            requester=requester(),
        )
    )

    authorization_id = (
        request.authorization
        .authorization_id
    )

    approval_gateway.approve(
        authorization_id,
        approver=senior(),
        expected_version=(
            authorization_store
            .get_record_version(
                authorization_id
            )
        ),
        idempotency_key=(
            "h32-4-revoke-approval"
        ),
    )

    authorization_store.revoke(
        authorization_id,
        actor=senior(),
        reason="H32.4 revocation test",
    )

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="authorization must be approved",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=
                authorization_id,
            plan=plan,
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert (
        stored.status
        == AuthorizationStatus.REVOKED
    )
    assert stored.consumed is False
    assert stored.execution_allowed is False


def test_expired_authorization_is_blocked(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    with authorization_store._connect() as connection:
        connection.execute(
            """
            UPDATE execution_authorizations
            SET expires_at = ?
            WHERE authorization_id = ?
            """,
            (
                (
                    datetime.now(
                        timezone.utc
                    )
                    - timedelta(minutes=1)
                ).isoformat(),
                authorization_id,
            ),
        )
        connection.commit()

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.is_expired is True

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="not usable",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=
                authorization_id,
            plan=plan,
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is False


def test_automatic_execution_plan_is_blocked(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    plan.automatic_execution_allowed = True

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="Automatic device execution",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=
                authorization_id,
            plan=plan,
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is False


def test_non_dry_run_plan_is_blocked(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    plan.dry_run_only = False

    with pytest.raises(
        SafeDecisionExecutionNotAllowed,
        match="dry-run",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=authorization_id,
            plan=plan,
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is False


def test_mismatched_decision_id_is_blocked(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    plan.decision_id = "decision:different"

    with pytest.raises(
        SafeDecisionExecutionBindingError,
        match="decision_id",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=authorization_id,
            plan=plan,
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is False


def test_mismatched_plan_id_is_blocked(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    plan.plan_id = "execution-plan:different"

    with pytest.raises(
        SafeDecisionExecutionBindingError,
        match="plan_id",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=authorization_id,
            plan=plan,
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is False


def test_verification_failure_marks_action_failed(
    tmp_path,
) -> None:
    (
        action_service,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
        fail_step_ids={"step:4"},
    )

    assert (
        result.simulation.status
        == SimulationStatus.ROLLED_BACK
    )

    assert result.simulation.rollback_performed is True

    assert (
        result.action.status
        == DecisionActionStatus.FAILED
    )

    assert (
        result.authorization.status
        == AuthorizationStatus.USED
    )

    assert result.authorization.consumed is True

    loaded_action = (
        action_service.get_action(
            action.decision_id
        )
    )

    assert (
        loaded_action.status
        == DecisionActionStatus.FAILED
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
        "consumed",
    ]


def test_failure_before_command_marks_action_failed(
    tmp_path,
) -> None:
    (
        _,
        _,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
        fail_step_ids={"step:1"},
    )

    assert (
        result.simulation.status
        == SimulationStatus.FAILED
    )

    assert result.simulation.rollback_performed is False

    assert (
        result.action.status
        == DecisionActionStatus.FAILED
    )


def test_result_serializes(
    tmp_path,
) -> None:
    (
        _,
        _,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
    )

    payload = result.to_dict()

    assert (
        payload["action"]["status"]
        == "completed"
    )

    assert (
        payload["authorization"]["status"]
        == "used"
    )

    assert (
        payload["simulation"]["status"]
        == "completed"
    )

    assert (
        payload["simulation"]["dry_run"]
        is True
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_execution_releases_lease(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
        owner_id="worker:primary",
    )

    assert result.lease.status.value == "released"
    assert result.lease.owner_id == "worker:primary"
    assert result.lease.lease_version == 2
    assert result.lease.is_active is False

    lease_store = ExecutionLeaseStore(
        authorization_store.database_path
    )

    events = lease_store.events(
        result.lease.lease_id
    )

    assert [
        event["event_type"]
        for event in events
    ] == [
        "acquired",
        "released",
    ]


def test_active_lease_blocks_second_worker(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    lease_store = ExecutionLeaseStore(
        authorization_store.database_path
    )

    held = lease_store.acquire(
        authorization_id,
        owner_id="worker:first",
        ttl_seconds=60,
    )

    from app.models.execution_lease import (
        LeaseConflict,
    )

    with pytest.raises(
        LeaseConflict,
    ) as exc:
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=authorization_id,
            plan=plan,
            owner_id="worker:second",
        )

    assert exc.value.owner_id == "worker:first"

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is False

    lease_store.release(
        held.lease_id,
        lease_token=held.lease_token,
        expected_version=held.lease_version,
    )


def test_execution_result_hides_lease_token(
    tmp_path,
) -> None:
    (
        _,
        _,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
    )

    payload = result.to_dict()

    assert "lease_token" not in payload["lease"]
    assert payload["lease"]["token_exposed"] is False
    assert payload["safety"]["lease_enforced"] is True


def test_invalid_lease_owner_is_rejected(
    tmp_path,
) -> None:
    (
        _,
        authorization_store,
        execution_bridge,
        action,
        plan,
        authorization_id,
    ) = prepare_approved_execution(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="owner_id",
    ):
        execution_bridge.execute(
            decision_id=action.decision_id,
            authorization_id=authorization_id,
            plan=plan,
            owner_id=" ",
        )

    stored = authorization_store.get(
        authorization_id
    )

    assert stored is not None
    assert stored.consumed is False


def test_bridge_requires_shared_database(
    tmp_path,
) -> None:
    authorization_database = (
        tmp_path / "authorization.db"
    )

    other_database = (
        tmp_path / "other.db"
    )

    action_service = DecisionActionService()

    authorization_store = (
        ExecutionAuthorizationStore(
            authorization_database
        )
    )

    ExecutionAuthorizationStore(
        other_database
    )

    lease_store = ExecutionLeaseStore(
        other_database
    )

    with pytest.raises(
        ValueError,
        match="same database",
    ):
        SafeDecisionExecutionBridge(
            action_service=action_service,
            authorization_store=(
                authorization_store
            ),
            lease_store=lease_store,
        )
