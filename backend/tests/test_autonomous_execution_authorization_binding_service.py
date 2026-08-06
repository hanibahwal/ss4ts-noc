from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionAuthorization,
    ExecutionRiskClass,
)
from app.services.autonomous_authorization_intent_audit import (
    verify_autonomous_authorization_intent_store,
)
from app.services.autonomous_authorization_intent_store import (
    AutonomousAuthorizationIntentStore,
)
from app.services.autonomous_execution_authorization_binding import (
    AutonomousExecutionAuthorizationBindingError,
    AutonomousExecutionAuthorizationBindingService,
    validate_execution_authorization_binding,
)
from tests.test_autonomous_authorization_intent_store import (
    make_intent,
)


NOW = datetime(
    2026,
    8,
    6,
    22,
    30,
    tzinfo=timezone.utc,
)


def requester() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:hani",
        display_name="Hani",
        role=ApprovalRole.NETWORK_ENGINEER,
    )


def make_authorization(
    *,
    risk_class: ExecutionRiskClass = (
        ExecutionRiskClass.MEDIUM
    ),
    **overrides,
) -> ExecutionAuthorization:
    values = {
        "authorization_id":
            "authorization:h25-binding",
        "plan_id":
            "execution-plan:h25-binding",
        "decision_id":
            "decision:h25-binding",
        "source_node_id":
            "device:test",
        "requester":
            requester(),
        "risk_class":
            risk_class,
        "status":
            AuthorizationStatus.PENDING,
        "decision":
            AuthorizationDecision.REQUIRE_APPROVAL,
        "requested_at":
            NOW,
        "expires_at":
            NOW + timedelta(
                minutes=30
            ),
        "dry_run_required":
            True,
        "rollback_required":
            True,
        "verification_required":
            True,
        "execution_allowed":
            False,
        "one_time_use":
            True,
        "consumed":
            False,
        "policy_reasons": [
            "Human approval required",
        ],
        "metadata": {
            "execution_enabled": False,
            "network_io_performed": False,
            "device_command_executed": False,
        },
    }

    values.update(
        overrides
    )

    return ExecutionAuthorization(
        **values
    )


def make_verified_inputs(
    tmp_path,
):
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path
    )

    record = store.append(
        intent=intent
    )

    audit = (
        verify_autonomous_authorization_intent_store(
            store,
            audited_at=NOW,
        )
    )

    authorization = make_authorization(
        risk_class=intent.risk_class
    )

    return (
        record,
        audit,
        authorization,
    )


def test_validate_and_bind(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    binding = (
        AutonomousExecutionAuthorizationBindingService()
        .validate_and_bind(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=authorization,
            binding_id=(
                "autonomous-execution-authorization-"
                "binding:service-test"
            ),
            created_at=NOW,
        )
    )

    assert (
        binding.authorization_intent_id
        == record.authorization_intent_id
    )

    assert (
        binding.intent_record_hash
        == record.record_hash
    )

    assert (
        binding.intent_audit_id
        == audit.audit_id
    )

    assert (
        binding.execution_authorization_id
        == authorization.authorization_id
    )

    assert (
        binding.binding_fingerprint
        == binding.calculate_fingerprint()
    )

    assert binding.can_execute is False


def test_functional_entrypoint(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    binding = (
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=authorization,
            created_at=NOW,
        )
    )

    assert (
        binding.authorization_status
        is AuthorizationStatus.PENDING
    )

    assert (
        binding.authorization_decision
        is AuthorizationDecision.REQUIRE_APPROVAL
    )


def test_approved_authorization_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    unsafe = deepcopy(
        authorization
    )

    unsafe.status = (
        AuthorizationStatus.APPROVED
    )

    unsafe.approver = ApprovalIdentity(
        identity_id="user:senior",
        display_name="Senior Engineer",
        role=ApprovalRole.SENIOR_ENGINEER,
    )

    unsafe.approved_at = NOW

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="status must be pending",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=unsafe,
            created_at=NOW,
        )


def test_allowed_decision_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    unsafe = deepcopy(
        authorization
    )

    unsafe.decision = (
        AuthorizationDecision.ALLOW
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="decision must require approval",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=unsafe,
            created_at=NOW,
        )


def test_execution_allowed_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    unsafe = deepcopy(
        authorization
    )

    unsafe.execution_allowed = True

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="allows execution",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=unsafe,
            created_at=NOW,
        )


def test_consumed_authorization_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    unsafe = deepcopy(
        authorization
    )

    unsafe.consumed = True

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="already consumed",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=unsafe,
            created_at=NOW,
        )

def test_expired_authorization_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    expired = replace(
        authorization,
        expires_at=(
            NOW - timedelta(
                seconds=1
            )
        ),
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="expired",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=expired,
            created_at=NOW,
        )


def test_risk_mismatch_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    different_risk_class = (
        ExecutionRiskClass.CRITICAL
        if authorization.risk_class
        is not ExecutionRiskClass.CRITICAL
        else ExecutionRiskClass.LOW
    )

    mismatched = replace(
        authorization,
        risk_class=different_risk_class,
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="risk class",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=mismatched,
            created_at=NOW,
        )


def test_policy_mismatch_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    mismatched = replace(
        authorization,
        dry_run_required=False,
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="dry_run_required",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=mismatched,
            created_at=NOW,
        )


def test_invalid_audit_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    invalid_audit = replace(
        audit,
        record_hashes_valid=False,
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="audit is invalid",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=invalid_audit,
            execution_authorization=authorization,
            created_at=NOW,
        )


def test_record_outside_audit_range_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    invalid_audit = replace(
        audit,
        first_sequence_number=2,
        last_sequence_number=3,
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="outside",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=invalid_audit,
            execution_authorization=authorization,
            created_at=NOW,
        )


def test_tampered_record_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    tampered = replace(
        record,
        record_hash="f" * 64,
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="record hash",
    ):
        validate_execution_authorization_binding(
            intent_record=tampered,
            intent_audit=audit,
            execution_authorization=authorization,
            created_at=NOW,
        )


def test_unsafe_metadata_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    unsafe = replace(
        authorization,
        metadata={
            **authorization.metadata,
            "execution_enabled": True,
        },
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingError,
        match="unsafe metadata",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=unsafe,
            created_at=NOW,
        )


def test_invalid_argument_types_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    service = (
        AutonomousExecutionAuthorizationBindingService()
    )

    with pytest.raises(
        TypeError,
        match="intent_record",
    ):
        service.validate_and_bind(
            intent_record="invalid",
            intent_audit=audit,
            execution_authorization=authorization,
            created_at=NOW,
        )

    with pytest.raises(
        TypeError,
        match="intent_audit",
    ):
        service.validate_and_bind(
            intent_record=record,
            intent_audit="invalid",
            execution_authorization=authorization,
            created_at=NOW,
        )

    with pytest.raises(
        TypeError,
        match="execution_authorization",
    ):
        service.validate_and_bind(
            intent_record=record,
            intent_audit=audit,
            execution_authorization="invalid",
            created_at=NOW,
        )


def test_empty_binding_id_rejected(
    tmp_path,
) -> None:
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="binding_id",
    ):
        validate_execution_authorization_binding(
            intent_record=record,
            intent_audit=audit,
            execution_authorization=authorization,
            binding_id=" ",
            created_at=NOW,
        )
