from __future__ import annotations

import json
import sqlite3

import pytest

from app.models.decision_action import (
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionTarget,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
)
from app.services.decision_action_service import (
    DecisionActionService,
)
from app.services.decision_approval_gateway import (
    DecisionApprovalGateway,
)
from app.services.decision_audit_store import (
    DecisionAuditStore,
)
from app.services.decision_execution_evidence import (
    DecisionExecutionEvidenceBindingError,
    DecisionExecutionEvidenceBuilder,
)
from app.services.execution_authorization_store import (
    ExecutionAuthorizationStore,
)
from app.services.execution_lease_store import (
    ExecutionLeaseStore,
)
from app.services.safe_decision_execution_bridge import (
    SafeDecisionExecutionBridge,
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


def prepare_execution(
    tmp_path,
):
    authorization_database = (
        tmp_path / "authorization.db"
    )

    audit_database = (
        tmp_path / "audit.db"
    )

    action_service = DecisionActionService()

    authorization_store = (
        ExecutionAuthorizationStore(
            authorization_database
        )
    )

    lease_store = ExecutionLeaseStore(
        authorization_database
    )

    approval_gateway = DecisionApprovalGateway(
        action_service=action_service,
        authorization_store=authorization_store,
    )

    execution_bridge = (
        SafeDecisionExecutionBridge(
            action_service=action_service,
            authorization_store=
                authorization_store,
            lease_store=lease_store,
        )
    )

    audit_store = DecisionAuditStore(
        audit_database
    )

    evidence_builder = (
        DecisionExecutionEvidenceBuilder(
            audit_store=audit_store,
            authorization_store=
                authorization_store,
            lease_store=lease_store,
        )
    )

    action = action_service.create_action(
        incident_id="incident:evidence-001",
        problem="Primary interface instability",
        recommendation=(
            "Simulate failover and verify "
            "backup connectivity"
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
            "execution-evidence-approval-001"
        ),
    )

    result = execution_bridge.execute(
        decision_id=action.decision_id,
        authorization_id=authorization_id,
        plan=plan,
        owner_id="worker:evidence",
    )

    return (
        authorization_store,
        lease_store,
        audit_store,
        evidence_builder,
        plan,
        result,
    )


def test_build_execution_evidence(
    tmp_path,
) -> None:
    (
        _,
        _,
        audit_store,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    bundle = builder.build(
        result=result,
        plan=plan,
    )

    assert bundle.verified is True
    assert bundle.audit.audit_id

    assert audit_store.verify(
        bundle.audit.audit_id
    ) is True


def test_evidence_contains_execution_data(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    bundle = builder.build(
        result=result,
        plan=plan,
    )

    audit = bundle.audit

    assert (
        audit.trace_payload[
            "decision_action"
        ]["decision_id"]
        == result.action.decision_id
    )

    assert (
        audit.explanation_payload[
            "approval_authorization"
        ]["authorization_id"]
        == result.authorization
        .authorization_id
    )

    assert (
        audit.execution_plan_payload[
            "plan_id"
        ]
        == plan.plan_id
    )

    assert (
        audit.simulation_payload[
            "simulation"
        ]["status"]
        == "completed"
    )


def test_authorization_events_are_included(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    bundle = builder.build(
        result=result,
        plan=plan,
    )

    event_types = [
        event["event_type"]
        for event in (
            bundle.audit
            .explanation_payload[
                "authorization_events"
            ]
        )
    ]

    assert event_types == [
        "created",
        "approved",
        "consumed",
    ]


def test_lease_events_are_included(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    bundle = builder.build(
        result=result,
        plan=plan,
    )

    event_types = [
        event["event_type"]
        for event in (
            bundle.audit
            .simulation_payload[
                "lease_events"
            ]
        )
    ]

    assert event_types == [
        "acquired",
        "released",
    ]


def test_lease_token_is_not_persisted(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    bundle = builder.build(
        result=result,
        plan=plan,
    )

    payload = bundle.to_dict()

    def contains_secret_key(
        value,
    ) -> bool:
        if isinstance(value, dict):
            if "lease_token" in value:
                return True

            return any(
                contains_secret_key(item)
                for item in value.values()
            )

        if isinstance(value, list):
            return any(
                contains_secret_key(item)
                for item in value
            )

        return False

    assert contains_secret_key(payload) is False

    released_lease = (
        bundle.audit
        .simulation_payload[
            "released_lease"
        ]
    )

    assert "lease_token" not in released_lease

    assert (
        released_lease[
            "token_exposed"
        ]
        is False
    )

    assert (
        payload["safety"][
            "lease_token_exposed"
        ]
        is False
    )


def test_tampering_fails_verification(
    tmp_path,
) -> None:
    (
        _,
        _,
        audit_store,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    bundle = builder.build(
        result=result,
        plan=plan,
    )

    with sqlite3.connect(
        audit_store.database_path
    ) as connection:
        tampered = dict(
            bundle.audit.simulation_payload
        )

        tampered["verification_summary"] = {
            "simulation_completed": False,
        }

        connection.execute(
            """
            UPDATE decision_audit_records
            SET simulation_payload = ?
            WHERE audit_id = ?
            """,
            (
                json.dumps(tampered),
                bundle.audit.audit_id,
            ),
        )

        connection.commit()

    assert audit_store.verify(
        bundle.audit.audit_id
    ) is False


def test_binding_mismatch_is_rejected(
    tmp_path,
) -> None:
    (
        _,
        _,
        audit_store,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    plan.plan_id = "execution-plan:different"

    with pytest.raises(
        DecisionExecutionEvidenceBindingError,
        match="plan_id",
    ):
        builder.build(
            result=result,
            plan=plan,
        )

    assert audit_store.count() == 0


def test_duplicate_audit_id_is_rejected(
    tmp_path,
) -> None:
    (
        _,
        _,
        audit_store,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    builder.build(
        result=result,
        plan=plan,
        audit_id="audit:fixed",
    )

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        builder.build(
            result=result,
            plan=plan,
            audit_id="audit:fixed",
        )

    assert audit_store.count() == 1


def test_bundle_serializes_integrity(
    tmp_path,
) -> None:
    (
        _,
        _,
        _,
        builder,
        plan,
        result,
    ) = prepare_execution(
        tmp_path
    )

    bundle = builder.build(
        result=result,
        plan=plan,
    )

    payload = bundle.to_dict()

    assert payload["verified"] is True

    assert (
        payload["integrity"]["status"]
        == "valid"
    )

    assert (
        payload["integrity"]
        ["checksum_algorithm"]
        == "sha256"
    )

    assert len(
        payload["integrity"]["checksum"]
    ) == 64
