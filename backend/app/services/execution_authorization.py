from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

from app.models.execution_authorization import (
    ApprovalIdentity,
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionAuthorization,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.services.execution_safety_policy import (
    ExecutionPolicyResult,
    evaluate_execution_policy,
)


DEFAULT_AUTHORIZATION_TTL_MINUTES = 30


class ExecutionAuthorizationService:
    """
    Build execution authorization requests from safe execution plans.

    This service creates authorization records only.
    It does not execute commands or contact network devices.
    """

    def __init__(
        self,
        *,
        ttl_minutes: int = (
            DEFAULT_AUTHORIZATION_TTL_MINUTES
        ),
    ) -> None:
        ttl_minutes = int(
            ttl_minutes
        )

        if ttl_minutes < 1:
            raise ValueError(
                "ttl_minutes must be at least 1"
            )

        if ttl_minutes > 1440:
            raise ValueError(
                "ttl_minutes must not exceed 1440"
            )

        self.ttl_minutes = ttl_minutes

    @staticmethod
    def _initial_status(
        policy: ExecutionPolicyResult,
    ) -> AuthorizationStatus:
        if (
            policy.decision
            == AuthorizationDecision.DENY
        ):
            return AuthorizationStatus.REJECTED

        if (
            policy.decision
            == AuthorizationDecision.ALLOW
            and policy.execution_allowed
        ):
            return AuthorizationStatus.APPROVED

        return AuthorizationStatus.PENDING

    def build(
        self,
        plan: ExecutionPlan,
        *,
        requester: ApprovalIdentity,
    ) -> ExecutionAuthorization:
        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "ExecutionAuthorizationService "
                "requires an ExecutionPlan"
            )

        if not isinstance(
            requester,
            ApprovalIdentity,
        ):
            raise TypeError(
                "requester must be "
                "an ApprovalIdentity"
            )

        policy = evaluate_execution_policy(
            plan,
            requester=requester,
        )

        now = datetime.now(
            timezone.utc
        )

        status = self._initial_status(
            policy
        )

        rejection_reason = None

        if (
            status
            == AuthorizationStatus.REJECTED
        ):
            rejection_reason = (
                "; ".join(policy.reasons)
                or "Execution policy denied the plan"
            )

        execution_allowed = bool(
            policy.execution_allowed
            and status
            == AuthorizationStatus.APPROVED
        )

        approver = (
            requester
            if status
            == AuthorizationStatus.APPROVED
            else None
        )

        approved_at = (
            now
            if status
            == AuthorizationStatus.APPROVED
            else None
        )

        return ExecutionAuthorization(
            authorization_id=(
                f"authorization:"
                f"{now.strftime('%Y%m%dT%H%M%S%fZ')}:"
                f"{uuid4().hex[:12]}"
            ),
            plan_id=plan.plan_id,
            decision_id=plan.decision_id,
            source_node_id=plan.source_node_id,
            requester=requester,
            approver=approver,
            risk_class=policy.risk_class,
            status=status,
            decision=policy.decision,
            requested_at=now,
            approved_at=approved_at,
            expires_at=(
                now
                + timedelta(
                    minutes=self.ttl_minutes
                )
            ),
            rejection_reason=rejection_reason,
            dry_run_required=
                policy.dry_run_required,
            rollback_required=
                policy.rollback_required,
            verification_required=
                policy.verification_required,
            execution_allowed=
                execution_allowed,
            one_time_use=True,
            consumed=False,
            confidence_percent=float(
                plan.metadata.get(
                    "confidence_percent",
                    plan.metadata.get(
                        "confidence",
                        0.0,
                    ),
                )
            ),
            policy_reasons=
                policy.reasons,
            metadata={
                "policy_decision":
                    policy.decision.value,
                "required_role":
                    policy.required_role.value,
                "approval_required":
                    policy.approval_required,
                "mutating_step_count":
                    policy.metadata.get(
                        "mutating_step_count",
                        plan.mutating_step_count,
                    ),
                "dry_run_only":
                    plan.dry_run_only,
                "automatic_execution_allowed":
                    plan
                    .automatic_execution_allowed,
                "execution_enabled":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        )


def build_execution_authorization(
    plan: ExecutionPlan,
    *,
    requester: ApprovalIdentity,
    ttl_minutes: int = (
        DEFAULT_AUTHORIZATION_TTL_MINUTES
    ),
) -> ExecutionAuthorization:
    return ExecutionAuthorizationService(
        ttl_minutes=ttl_minutes
    ).build(
        plan,
        requester=requester,
    )
