from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionAuthorization,
    ExecutionRiskClass,
)


def requester() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:hani",
        display_name="Hani",
        role=ApprovalRole.NETWORK_ENGINEER,
        email="hani@example.com",
    )


def approver() -> ApprovalIdentity:
    return ApprovalIdentity(
        identity_id="user:senior",
        display_name="Senior Engineer",
        role=ApprovalRole.SENIOR_ENGINEER,
    )


def make_authorization(
    **overrides,
) -> ExecutionAuthorization:
    values = {
        "authorization_id":
            "authorization:1",
        "plan_id":
            "execution-plan:device:core",
        "decision_id":
            "decision:device:core",
        "source_node_id":
            "device:core",
        "requester":
            requester(),
        "risk_class":
            ExecutionRiskClass.MEDIUM,
        "status":
            AuthorizationStatus.PENDING,
        "decision":
            AuthorizationDecision
            .REQUIRE_APPROVAL,
        "dry_run_required":
            True,
        "rollback_required":
            True,
        "verification_required":
            True,
        "execution_allowed":
            False,
        "policy_reasons": [
            "Mutating step requires approval",
        ],
    }

    values.update(
        overrides
    )

    return ExecutionAuthorization(
        **values
    )


def test_identity_serialization() -> None:
    payload = requester().to_dict()

    assert (
        payload["identity_id"]
        == "user:hani"
    )

    assert (
        payload["role"]
        == "network_engineer"
    )


def test_pending_authorization_is_not_usable() -> None:
    authorization = make_authorization()

    assert authorization.is_usable is False

    assert (
        authorization
        .requires_human_approval
        is True
    )


def test_approved_authorization_is_usable() -> None:
    now = datetime.now(
        timezone.utc
    )

    authorization = make_authorization(
        status=AuthorizationStatus.APPROVED,
        decision=AuthorizationDecision.ALLOW,
        approver=approver(),
        approved_at=now,
        expires_at=(
            now
            + timedelta(minutes=30)
        ),
        execution_allowed=True,
    )

    assert authorization.is_usable is True

    payload = authorization.to_dict()

    assert payload["status"] == "approved"
    assert payload["decision"] == "allow"
    assert payload["is_usable"] is True


def test_approved_requires_approver() -> None:
    with pytest.raises(
        ValueError,
        match="approver",
    ):
        make_authorization(
            status=(
                AuthorizationStatus
                .APPROVED
            ),
            decision=(
                AuthorizationDecision
                .ALLOW
            ),
            approved_at=datetime.now(
                timezone.utc
            ),
            execution_allowed=True,
        )


def test_approved_requires_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="approved_at",
    ):
        make_authorization(
            status=(
                AuthorizationStatus
                .APPROVED
            ),
            decision=(
                AuthorizationDecision
                .ALLOW
            ),
            approver=approver(),
            execution_allowed=True,
        )


def test_rejected_requires_reason() -> None:
    with pytest.raises(
        ValueError,
        match="reason",
    ):
        make_authorization(
            status=(
                AuthorizationStatus
                .REJECTED
            ),
            decision=(
                AuthorizationDecision
                .DENY
            ),
        )


def test_execution_requires_approval() -> None:
    with pytest.raises(
        ValueError,
        match="without approval",
    ):
        make_authorization(
            execution_allowed=True,
        )


def test_expired_authorization_is_not_usable() -> None:
    now = datetime.now(
        timezone.utc
    )

    authorization = make_authorization(
        status=AuthorizationStatus.APPROVED,
        decision=AuthorizationDecision.ALLOW,
        approver=approver(),
        approved_at=(
            now
            - timedelta(minutes=10)
        ),
        expires_at=(
            now
            - timedelta(minutes=1)
        ),
        execution_allowed=True,
    )

    assert authorization.is_expired is True
    assert authorization.is_usable is False


def test_consumed_authorization_is_not_usable() -> None:
    now = datetime.now(
        timezone.utc
    )

    authorization = make_authorization(
        status=AuthorizationStatus.USED,
        decision=AuthorizationDecision.ALLOW,
        approver=approver(),
        approved_at=now,
        execution_allowed=False,
        consumed=True,
    )

    assert authorization.is_usable is False


def test_high_risk_requires_rollback() -> None:
    with pytest.raises(
        ValueError,
        match="requires rollback",
    ):
        make_authorization(
            risk_class=(
                ExecutionRiskClass.HIGH
            ),
            rollback_required=False,
        )


def test_high_risk_requires_verification() -> None:
    with pytest.raises(
        ValueError,
        match="requires verification",
    ):
        make_authorization(
            risk_class=(
                ExecutionRiskClass.CRITICAL
            ),
            verification_required=False,
        )


def test_policy_reasons_are_deduplicated() -> None:
    authorization = make_authorization(
        policy_reasons=[
            "Approval required",
            "Approval required",
            "Rollback required",
        ]
    )

    assert authorization.policy_reasons == [
        "Approval required",
        "Rollback required",
    ]
