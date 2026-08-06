from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.autonomous_operation_proposal import (
    AutonomousOperationMode,
    AutonomousOperationProposal,
    AutonomousPolicyStatus,
    AutonomousProposalRiskLevel,
)
from app.models.decision_action import (
    DecisionAction,
    DecisionActionRiskLevel,
)
from app.models.execution_plan import (
    ExecutionPlan,
)


SERVICE_NAME = (
    "SS4TS Autonomous Proposal Decision Binding"
)

SERVICE_VERSION = "1.0.0"


RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _enum_value(
    value: Any,
) -> str:
    raw = getattr(
        value,
        "value",
        value,
    )

    return str(
        raw
    ).strip().lower()


@dataclass(slots=True)
class AutonomousProposalBindingResult:
    proposal_id: str
    decision_id: str | None
    plan_id: str | None

    binding_valid: bool
    binding_errors: tuple[str, ...]

    decision_consistent: bool
    plan_consistent: bool
    target_consistent: bool
    operation_consistent: bool
    confidence_consistent: bool
    risk_consistent: bool

    policy_review_allowed: bool
    proposal_not_expired: bool
    human_approval_required: bool
    dry_run_only: bool

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "proposal_id":
                self.proposal_id,
            "decision_id":
                self.decision_id,
            "plan_id":
                self.plan_id,
            "binding_valid":
                self.binding_valid,
            "binding_errors":
                list(
                    self.binding_errors
                ),
            "checks": {
                "decision_consistent":
                    self.decision_consistent,
                "plan_consistent":
                    self.plan_consistent,
                "target_consistent":
                    self.target_consistent,
                "operation_consistent":
                    self.operation_consistent,
                "confidence_consistent":
                    self.confidence_consistent,
                "risk_consistent":
                    self.risk_consistent,
                "policy_review_allowed":
                    self.policy_review_allowed,
                "proposal_not_expired":
                    self.proposal_not_expired,
                "human_approval_required":
                    self.human_approval_required,
                "dry_run_only":
                    self.dry_run_only,
            },
            "can_execute":
                False,
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "binding_validation_only":
                    True,
                "execution_authority":
                    False,
                "authorization_created":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
                "controlled_execution_required":
                    True,
            },
        }


class AutonomousProposalBinding:
    def validate(
        self,
        *,
        proposal: AutonomousOperationProposal,
        action: DecisionAction,
        plan: ExecutionPlan,
    ) -> AutonomousProposalBindingResult:
        if not isinstance(
            proposal,
            AutonomousOperationProposal,
        ):
            raise TypeError(
                "proposal must be an "
                "AutonomousOperationProposal"
            )

        if not isinstance(
            action,
            DecisionAction,
        ):
            raise TypeError(
                "action must be a DecisionAction"
            )

        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan must be an ExecutionPlan"
            )

        errors: list[str] = []

        decision_consistent = (
            proposal.decision_id
            is not None
            and proposal.decision_id
            == action.decision_id
            and proposal.decision_id
            == plan.decision_id
        )

        if not decision_consistent:
            errors.append(
                "Decision identifiers do not match"
            )

        plan_consistent = (
            proposal.plan_id
            is not None
            and proposal.plan_id
            == plan.plan_id
        )

        if not plan_consistent:
            errors.append(
                "Execution plan identifier does not match"
            )

        action_target_id = getattr(
            action.target,
            "device_id",
            None,
        )

        target_consistent = (
            proposal.target_node_id
            == action_target_id
            and proposal.target_node_id
            == plan.source_node_id
        )

        if not target_consistent:
            errors.append(
                "Proposal target does not match "
                "the action and execution plan"
            )

        action_type = getattr(
            action.command,
            "action_type",
            None,
        )

        operation_consistent = (
            str(
                proposal.operation_type
            ).strip().lower()
            == str(
                action_type
            ).strip().lower()
        )

        if not operation_consistent:
            errors.append(
                "Proposal operation type does not "
                "match the decision action"
            )

        confidence_consistent = (
            proposal.confidence_percent
            <= action.confidence_percent
        )

        if not confidence_consistent:
            errors.append(
                "Proposal confidence exceeds "
                "decision confidence"
            )

        proposal_risk = _enum_value(
            proposal.risk_level
        )

        action_risk = _enum_value(
            action.risk_level
        )

        risk_consistent = (
            RISK_RANK.get(
                proposal_risk,
                999,
            )
            >= RISK_RANK.get(
                action_risk,
                999,
            )
        )

        if not risk_consistent:
            errors.append(
                "Proposal risk understates "
                "decision action risk"
            )

        policy_review_allowed = (
            proposal.policy_status
            is AutonomousPolicyStatus
            .ALLOWED_FOR_REVIEW
            and proposal.review_allowed
        )

        if not policy_review_allowed:
            errors.append(
                "Proposal policy does not allow review"
            )

        proposal_not_expired = (
            not proposal.is_expired
        )

        if not proposal_not_expired:
            errors.append(
                "Proposal has expired"
            )

        human_approval_required = (
            proposal.requires_human_approval
            and proposal.operating_mode
            is AutonomousOperationMode
            .APPROVAL_CANDIDATE
            and bool(
                getattr(
                    action,
                    "approval_required",
                    False,
                )
            )
            and bool(
                getattr(
                    plan,
                    "approval_required",
                    False,
                )
            )
        )

        if not human_approval_required:
            errors.append(
                "Human approval boundary is incomplete"
            )

        dry_run_only = bool(
            getattr(
                plan,
                "dry_run_only",
                False,
            )
        )

        if not dry_run_only:
            errors.append(
                "Execution plan must be dry-run-only"
            )

        unique_errors = tuple(
            dict.fromkeys(
                errors
            )
        )

        return AutonomousProposalBindingResult(
            proposal_id=proposal.proposal_id,
            decision_id=proposal.decision_id,
            plan_id=proposal.plan_id,
            binding_valid=(
                len(
                    unique_errors
                )
                == 0
            ),
            binding_errors=unique_errors,
            decision_consistent=(
                decision_consistent
            ),
            plan_consistent=(
                plan_consistent
            ),
            target_consistent=(
                target_consistent
            ),
            operation_consistent=(
                operation_consistent
            ),
            confidence_consistent=(
                confidence_consistent
            ),
            risk_consistent=(
                risk_consistent
            ),
            policy_review_allowed=(
                policy_review_allowed
            ),
            proposal_not_expired=(
                proposal_not_expired
            ),
            human_approval_required=(
                human_approval_required
            ),
            dry_run_only=dry_run_only,
        )
