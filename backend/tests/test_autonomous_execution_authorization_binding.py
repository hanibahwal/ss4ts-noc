from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.models.autonomous_execution_authorization_binding import (
    AutonomousExecutionAuthorizationBinding,
)
from app.models.execution_authorization import (
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionRiskClass,
)


NOW = datetime(
    2026,
    8,
    6,
    22,
    5,
    tzinfo=timezone.utc,
)


def make_binding(
) -> AutonomousExecutionAuthorizationBinding:
    values = {
        "binding_id":
            "autonomous-execution-authorization-binding:test",
        "authorization_intent_id":
            "autonomous-authorization-intent:test",
        "intent_record_hash":
            "1" * 64,
        "intent_bridge_fingerprint":
            "2" * 64,
        "intent_audit_id":
            "autonomous-authorization-intent-audit:test",
        "intent_audit_valid":
            True,
        "execution_authorization_id":
            "authorization:test",
        "plan_id":
            "execution-plan:test",
        "decision_id":
            "decision:test",
        "risk_class":
            ExecutionRiskClass.MEDIUM,
        "authorization_status":
            AuthorizationStatus.PENDING,
        "authorization_decision":
            AuthorizationDecision.REQUIRE_APPROVAL,
        "created_at":
            NOW,
        "expires_at":
            NOW + timedelta(
                minutes=30
            ),
    }

    provisional = (
        AutonomousExecutionAuthorizationBinding.__new__(
            AutonomousExecutionAuthorizationBinding
        )
    )

    for field, value in values.items():
        object.__setattr__(
            provisional,
            field,
            value,
        )

    object.__setattr__(
        provisional,
        "binding_fingerprint",
        "",
    )

    fingerprint = (
        provisional.calculate_fingerprint()
    )

    return AutonomousExecutionAuthorizationBinding(
        **values,
        binding_fingerprint=fingerprint,
    )


def test_create_binding_contract() -> None:
    binding = make_binding()

    assert isinstance(
        binding,
        AutonomousExecutionAuthorizationBinding,
    )

    assert (
        binding.binding_fingerprint
        == binding.calculate_fingerprint()
    )


def test_binding_preserves_authorization_identity() -> None:
    binding = make_binding()

    assert (
        binding.execution_authorization_id
        == "authorization:test"
    )

    assert binding.plan_id == "execution-plan:test"
    assert binding.decision_id == "decision:test"


def test_binding_preserves_intent_integrity() -> None:
    binding = make_binding()

    assert (
        binding.authorization_intent_id
        == "autonomous-authorization-intent:test"
    )

    assert binding.intent_record_hash == "1" * 64

    assert (
        binding.intent_bridge_fingerprint
        == "2" * 64
    )

    assert binding.intent_audit_valid is True


def test_binding_requires_pending_approval() -> None:
    binding = make_binding()

    assert (
        binding.authorization_status
        is AuthorizationStatus.PENDING
    )

    assert (
        binding.authorization_decision
        is AuthorizationDecision.REQUIRE_APPROVAL
    )


def test_binding_is_never_executable() -> None:
    binding = make_binding()

    assert (
        binding.execution_authorization_created
        is True
    )

    assert (
        binding.authorization_binding_created
        is True
    )

    assert binding.authorization_approved is False

    assert (
        binding.authorization_token_created
        is False
    )

    assert binding.approval_claim_created is False
    assert binding.execution_lease_created is False
    assert binding.execution_allowed is False
    assert binding.can_execute is False


def test_binding_safety_metadata() -> None:
    payload = make_binding().to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "authorization_binding_only":
            True,
        "execution_authorization_created":
            True,
        "execution_authorization_stored":
            False,
        "authorization_approved":
            False,
        "authorization_token_created":
            False,
        "approval_claim_created":
            False,
        "execution_lease_created":
            False,
        "execution_allowed":
            False,
        "execution_approved":
            False,
        "authorization_consumed":
            False,
        "simulation_started":
            False,
        "network_io_performed":
            False,
        "device_access_performed":
            False,
        "command_generated":
            False,
        "device_command_executed":
            False,
    }


def test_invalid_intent_audit_rejected() -> None:
    binding = make_binding()

    with pytest.raises(
        ValueError,
        match="intent_audit_valid",
    ):
        replace(
            binding,
            intent_audit_valid=False,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "authorization_status",
            AuthorizationStatus.APPROVED,
        ),
        (
            "authorization_decision",
            AuthorizationDecision.ALLOW,
        ),
    ],
)
def test_approved_or_allowed_binding_rejected(
    field,
    value,
) -> None:
    binding = make_binding()

    with pytest.raises(
        ValueError,
    ):
        replace(
            binding,
            **{
                field: value,
            },
        )


def test_expired_window_rejected() -> None:
    binding = make_binding()

    with pytest.raises(
        ValueError,
        match="expires_at",
    ):
        replace(
            binding,
            expires_at=NOW,
        )


def test_invalid_hash_rejected() -> None:
    binding = make_binding()

    with pytest.raises(
        ValueError,
        match="intent_record_hash",
    ):
        replace(
            binding,
            intent_record_hash="invalid",
        )


def test_tampered_fingerprint_rejected() -> None:
    binding = make_binding()

    with pytest.raises(
        ValueError,
        match="binding_fingerprint",
    ):
        replace(
            binding,
            binding_fingerprint="f" * 64,
        )


def test_naive_datetime_rejected() -> None:
    binding = make_binding()

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        replace(
            binding,
            created_at=datetime(
                2026,
                8,
                6,
                22,
                5,
            ),
        )
