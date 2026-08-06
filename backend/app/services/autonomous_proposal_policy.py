from __future__ import annotations

from dataclasses import (
    dataclass,
)
from typing import Any

from app.models.autonomous_operation_proposal import (
    AutonomousOperationMode,
    AutonomousOperationProposal,
    AutonomousPolicyStatus,
    AutonomousProposalRiskLevel,
)


SERVICE_NAME = (
    "SS4TS Autonomous Proposal Policy"
)

SERVICE_VERSION = "1.0.0"


@dataclass(slots=True)
class AutonomousProposalPolicyResult:
    proposal_id: str
    policy_status: AutonomousPolicyStatus
    operating_mode: AutonomousOperationMode
    requires_human_approval: bool
    allowed_for_review: bool
    blocked: bool
    reasons: tuple[str, ...]
    confidence_threshold: float
    evaluated_confidence: float

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
            "policy_status":
                self.policy_status.value,
            "operating_mode":
                self.operating_mode.value,
            "requires_human_approval":
                self.requires_human_approval,
            "allowed_for_review":
                self.allowed_for_review,
            "blocked":
                self.blocked,
            "reasons":
                list(
                    self.reasons
                ),
            "confidence_threshold":
                self.confidence_threshold,
            "evaluated_confidence":
                self.evaluated_confidence,
            "can_execute":
                False,
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "policy_evaluation_only":
                    True,
                "execution_authority":
                    False,
                "human_approval_boundary":
                    True,
                "controlled_execution_required":
                    True,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        }


class AutonomousProposalPolicy:
    def __init__(
        self,
        *,
        minimum_confidence: float = 70.0,
    ) -> None:
        threshold = float(
            minimum_confidence
        )

        if not 0 <= threshold <= 100:
            raise ValueError(
                "minimum_confidence must be "
                "between 0 and 100"
            )

        self.minimum_confidence = round(
            threshold,
            2,
        )

    def evaluate(
        self,
        proposal: AutonomousOperationProposal,
    ) -> AutonomousProposalPolicyResult:
        if not isinstance(
            proposal,
            AutonomousOperationProposal,
        ):
            raise TypeError(
                "proposal must be an "
                "AutonomousOperationProposal"
            )

        reasons: list[str] = []

        if proposal.is_expired:
            reasons.append(
                "Proposal has expired"
            )

        if (
            proposal.confidence_percent
            < self.minimum_confidence
        ):
            reasons.append(
                "Confidence is below "
                "the policy threshold"
            )

        if (
            proposal.risk_level
            is AutonomousProposalRiskLevel
            .CRITICAL
        ):
            reasons.append(
                "Critical-risk proposals "
                "are blocked by policy"
            )

        forbidden_operations = {
            "auto_execute",
            "execute_now",
            "bypass_approval",
            "device_command",
            "routeros_command",
        }

        if (
            proposal.operation_type
            .strip()
            .lower()
            in forbidden_operations
        ):
            reasons.append(
                "Operation type is forbidden "
                "by autonomous policy"
            )

        blocked = bool(
            reasons
        )

        if blocked:
            policy_status = (
                AutonomousPolicyStatus
                .BLOCKED
            )

            operating_mode = (
                AutonomousOperationMode
                .ADVISORY_ONLY
            )

            allowed_for_review = False

        else:
            policy_status = (
                AutonomousPolicyStatus
                .ALLOWED_FOR_REVIEW
            )

            allowed_for_review = True

            if (
                proposal.risk_level
                in {
                    AutonomousProposalRiskLevel
                    .HIGH,
                    AutonomousProposalRiskLevel
                    .MEDIUM,
                }
            ):
                operating_mode = (
                    AutonomousOperationMode
                    .APPROVAL_CANDIDATE
                )

                reasons.append(
                    "Human approval required "
                    "before any execution workflow"
                )

            else:
                operating_mode = (
                    AutonomousOperationMode
                    .ADVISORY_ONLY
                )

                reasons.append(
                    "Proposal is advisory-only"
                )

        requires_human_approval = True

        return AutonomousProposalPolicyResult(
            proposal_id=proposal.proposal_id,
            policy_status=policy_status,
            operating_mode=operating_mode,
            requires_human_approval=(
                requires_human_approval
            ),
            allowed_for_review=(
                allowed_for_review
            ),
            blocked=blocked,
            reasons=tuple(
                dict.fromkeys(
                    reasons
                )
            ),
            confidence_threshold=(
                self.minimum_confidence
            ),
            evaluated_confidence=(
                proposal.confidence_percent
            ),
        )

    def apply(
        self,
        proposal: AutonomousOperationProposal,
    ) -> AutonomousProposalPolicyResult:
        result = self.evaluate(
            proposal
        )

        proposal.policy_status = (
            result.policy_status
        )

        proposal.operating_mode = (
            result.operating_mode
        )

        proposal.requires_human_approval = (
            True
        )

        proposal.policy_reasons = tuple(
            result.reasons
        )

        return result
