from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationDecision,
    ExecutionRiskClass,
)
from app.models.execution_plan import (
    ExecutionPlan,
    ExecutionStepType,
)


@dataclass(slots=True)
class ExecutionPolicyResult:
    decision: AuthorizationDecision
    risk_class: ExecutionRiskClass

    approval_required: bool
    dry_run_required: bool
    rollback_required: bool
    verification_required: bool

    required_role: ApprovalRole

    execution_allowed: bool = False

    reasons: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.reasons = list(
            dict.fromkeys(
                str(item).strip()
                for item in self.reasons
                if str(item).strip()
            )
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if (
            self.execution_allowed
            and self.decision
            != AuthorizationDecision.ALLOW
        ):
            raise ValueError(
                "Execution cannot be allowed "
                "unless policy decision is ALLOW"
            )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "decision":
                self.decision.value,
            "risk_class":
                self.risk_class.value,
            "approval_required":
                self.approval_required,
            "dry_run_required":
                self.dry_run_required,
            "rollback_required":
                self.rollback_required,
            "verification_required":
                self.verification_required,
            "required_role":
                self.required_role.value,
            "execution_allowed":
                self.execution_allowed,
            "reasons":
                list(self.reasons),
            "metadata":
                dict(self.metadata),
        }


class ExecutionSafetyPolicy:
    """
    Evaluate an execution plan without executing it.

    The policy engine only classifies risk and approval requirements.
    """

    @staticmethod
    def _mutating_steps(
        plan: ExecutionPlan,
    ):
        return [
            step
            for step in plan.steps
            if (
                step.step_type
                == ExecutionStepType.COMMAND
            )
        ]

    @staticmethod
    def _verification_present(
        plan: ExecutionPlan,
    ) -> bool:
        return any(
            step.step_type
            == ExecutionStepType.VERIFY
            for step in plan.steps
        )

    @staticmethod
    def _rollback_present(
        plan: ExecutionPlan,
    ) -> bool:
        mutating = (
            ExecutionSafetyPolicy
            ._mutating_steps(plan)
        )

        if not mutating:
            return True

        return all(
            step.reversible
            and bool(step.rollback_command)
            for step in mutating
        )

    @staticmethod
    def _unsafe_command_present(
        plan: ExecutionPlan,
    ) -> bool:
        return any(
            step.command
            and not step.command.startswith(
                "DRY_RUN_ONLY:"
            )
            for step in (
                ExecutionSafetyPolicy
                ._mutating_steps(plan)
            )
        )

    @staticmethod
    def _classify_risk(
        plan: ExecutionPlan,
    ) -> ExecutionRiskClass:
        mutating = (
            ExecutionSafetyPolicy
            ._mutating_steps(plan)
        )

        if not mutating:
            return ExecutionRiskClass.READ_ONLY

        if len(mutating) == 1:
            return ExecutionRiskClass.MEDIUM

        if len(mutating) <= 3:
            return ExecutionRiskClass.HIGH

        return ExecutionRiskClass.CRITICAL

    @staticmethod
    def _required_role(
        risk_class: ExecutionRiskClass,
    ) -> ApprovalRole:
        mapping = {
            ExecutionRiskClass.READ_ONLY:
                ApprovalRole.NETWORK_ENGINEER,
            ExecutionRiskClass.LOW:
                ApprovalRole.NETWORK_ENGINEER,
            ExecutionRiskClass.MEDIUM:
                ApprovalRole.SENIOR_ENGINEER,
            ExecutionRiskClass.HIGH:
                ApprovalRole.CHANGE_MANAGER,
            ExecutionRiskClass.CRITICAL:
                ApprovalRole.ADMINISTRATOR,
        }

        return mapping.get(
            risk_class,
            ApprovalRole.ADMINISTRATOR,
        )

    def evaluate(
        self,
        plan: ExecutionPlan,
        *,
        requester: ApprovalIdentity,
    ) -> ExecutionPolicyResult:
        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "ExecutionSafetyPolicy requires "
                "an ExecutionPlan"
            )

        if not isinstance(
            requester,
            ApprovalIdentity,
        ):
            raise TypeError(
                "requester must be "
                "an ApprovalIdentity"
            )

        risk_class = self._classify_risk(
            plan
        )

        mutating_steps = self._mutating_steps(
            plan
        )

        rollback_present = (
            self._rollback_present(plan)
        )

        verification_present = (
            self._verification_present(plan)
        )

        unsafe_command = (
            self._unsafe_command_present(plan)
        )

        reasons: list[str] = []

        approval_required = bool(
            mutating_steps
        )

        dry_run_required = bool(
            mutating_steps
        )

        rollback_required = (
            risk_class
            in {
                ExecutionRiskClass.MEDIUM,
                ExecutionRiskClass.HIGH,
                ExecutionRiskClass.CRITICAL,
            }
        )

        verification_required = bool(
            mutating_steps
        )

        required_role = self._required_role(
            risk_class
        )

        if unsafe_command:
            reasons.append(
                "Unsafe command detected: "
                "DRY_RUN_ONLY prefix missing"
            )

            return ExecutionPolicyResult(
                decision=(
                    AuthorizationDecision.DENY
                ),
                risk_class=risk_class,
                approval_required=True,
                dry_run_required=True,
                rollback_required=
                    rollback_required,
                verification_required=
                    verification_required,
                required_role=
                    ApprovalRole.ADMINISTRATOR,
                execution_allowed=False,
                reasons=reasons,
                metadata={
                    "mutating_step_count":
                        len(mutating_steps),
                    "unsafe_command_present":
                        True,
                },
            )

        if (
            rollback_required
            and not rollback_present
        ):
            reasons.append(
                "Required rollback is missing"
            )

            return ExecutionPolicyResult(
                decision=(
                    AuthorizationDecision.DENY
                ),
                risk_class=risk_class,
                approval_required=True,
                dry_run_required=True,
                rollback_required=True,
                verification_required=
                    verification_required,
                required_role=required_role,
                execution_allowed=False,
                reasons=reasons,
                metadata={
                    "mutating_step_count":
                        len(mutating_steps),
                    "rollback_present":
                        False,
                },
            )

        if (
            verification_required
            and not verification_present
        ):
            reasons.append(
                "Required verification step "
                "is missing"
            )

            return ExecutionPolicyResult(
                decision=(
                    AuthorizationDecision.DENY
                ),
                risk_class=risk_class,
                approval_required=True,
                dry_run_required=True,
                rollback_required=
                    rollback_required,
                verification_required=True,
                required_role=required_role,
                execution_allowed=False,
                reasons=reasons,
                metadata={
                    "mutating_step_count":
                        len(mutating_steps),
                    "verification_present":
                        False,
                },
            )

        if not mutating_steps:
            reasons.append(
                "Read-only plan contains "
                "no mutating commands"
            )

            return ExecutionPolicyResult(
                decision=(
                    AuthorizationDecision.ALLOW
                ),
                risk_class=(
                    ExecutionRiskClass.READ_ONLY
                ),
                approval_required=False,
                dry_run_required=False,
                rollback_required=False,
                verification_required=False,
                required_role=(
                    ApprovalRole.NETWORK_ENGINEER
                ),
                execution_allowed=True,
                reasons=reasons,
                metadata={
                    "mutating_step_count": 0,
                    "read_only": True,
                },
            )

        if (
            risk_class
            == ExecutionRiskClass.CRITICAL
        ):
            reasons.append(
                "Critical plans cannot be "
                "automatically authorized"
            )

            return ExecutionPolicyResult(
                decision=(
                    AuthorizationDecision.DENY
                ),
                risk_class=risk_class,
                approval_required=True,
                dry_run_required=True,
                rollback_required=True,
                verification_required=True,
                required_role=(
                    ApprovalRole.ADMINISTRATOR
                ),
                execution_allowed=False,
                reasons=reasons,
                metadata={
                    "mutating_step_count":
                        len(mutating_steps),
                },
            )

        reasons.extend([
            "Mutating plan requires "
            "human approval",
            "Dry-run simulation required "
            "before execution",
        ])

        return ExecutionPolicyResult(
            decision=(
                AuthorizationDecision
                .REQUIRE_APPROVAL
            ),
            risk_class=risk_class,
            approval_required=True,
            dry_run_required=True,
            rollback_required=
                rollback_required,
            verification_required=True,
            required_role=required_role,
            execution_allowed=False,
            reasons=reasons,
            metadata={
                "mutating_step_count":
                    len(mutating_steps),
                "rollback_present":
                    rollback_present,
                "verification_present":
                    verification_present,
                "requester_role":
                    requester.role.value,
            },
        )


def evaluate_execution_policy(
    plan: ExecutionPlan,
    *,
    requester: ApprovalIdentity,
) -> ExecutionPolicyResult:
    return ExecutionSafetyPolicy().evaluate(
        plan,
        requester=requester,
    )
