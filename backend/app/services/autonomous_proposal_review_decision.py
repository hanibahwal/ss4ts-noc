from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from app.models.autonomous_proposal_review_decision import (
    AutonomousHumanReviewDecisionType,
    AutonomousProposalHumanReviewDecision,
)
from app.services.autonomous_proposal_review_queue import (
    AutonomousProposalReviewQueueItem,
    AutonomousReviewStatus,
)


SERVICE_NAME = (
    "SS4TS Autonomous Proposal Human Review Decision"
)

SERVICE_VERSION = "1.0.0"


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _utc_now(
) -> datetime:
    return datetime.now(
        timezone.utc
    )


def _normalize_required_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    normalized = str(
        value
    ).strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _resolve_decision(
    value: (
        AutonomousHumanReviewDecisionType
        | str
    ),
) -> AutonomousHumanReviewDecisionType:
    if isinstance(
        value,
        AutonomousHumanReviewDecisionType,
    ):
        return value

    try:
        return (
            AutonomousHumanReviewDecisionType(
                str(
                    value
                ).strip()
            )
        )

    except ValueError as exc:
        raise ValueError(
            "Unsupported human review decision"
        ) from exc


def _normalize_reviewed_at(
    value: datetime | None,
) -> datetime:
    resolved = (
        value
        or _utc_now()
    )

    if not isinstance(
        resolved,
        datetime,
    ):
        raise TypeError(
            "reviewed_at must be a datetime"
        )

    if resolved.tzinfo is None:
        resolved = resolved.replace(
            tzinfo=timezone.utc
        )

    return resolved.astimezone(
        timezone.utc
    )


class AutonomousProposalHumanReviewService:
    """
    Create an explicit human-originated review decision.

    Approval here only means that the proposal may enter a
    separate controlled authorization review. It does not create
    an authorization and cannot approve or perform execution.
    """

    @staticmethod
    def create_decision(
        *,
        queue_item: (
            AutonomousProposalReviewQueueItem
        ),
        reviewer_id: str,
        reviewer_name: str,
        decision: (
            AutonomousHumanReviewDecisionType
            | str
        ),
        reason: str,
        audit_id: str,
        audit_valid: bool,
        reviewed_at: datetime | None = None,
        review_decision_id: str | None = None,
    ) -> AutonomousProposalHumanReviewDecision:
        if not isinstance(
            queue_item,
            AutonomousProposalReviewQueueItem,
        ):
            raise TypeError(
                "queue_item must be an "
                "AutonomousProposalReviewQueueItem"
            )

        if (
            queue_item.review_status
            is not AutonomousReviewStatus
            .PENDING_REVIEW
        ):
            raise ValueError(
                "Only pending review queue items "
                "may receive a human decision"
            )

        if (
            queue_item.review_required
            is not True
        ):
            raise ValueError(
                "Queue item does not require "
                "human review"
            )

        if queue_item.can_execute:
            raise ValueError(
                "Executable queue items are not "
                "accepted"
            )

        if audit_valid is not True:
            raise ValueError(
                "A valid proposal audit is "
                "required"
            )

        resolved_reviewer_id = (
            _normalize_required_text(
                reviewer_id,
                field_name="reviewer_id",
            )
        )

        resolved_reviewer_name = (
            _normalize_required_text(
                reviewer_name,
                field_name="reviewer_name",
            )
        )

        resolved_reason = (
            _normalize_required_text(
                reason,
                field_name="reason",
            )
        )

        resolved_audit_id = (
            _normalize_required_text(
                audit_id,
                field_name="audit_id",
            )
        )

        resolved_decision = (
            _resolve_decision(
                decision
            )
        )

        resolved_reviewed_at = (
            _normalize_reviewed_at(
                reviewed_at
            )
        )

        resolved_decision_id = (
            _normalize_required_text(
                review_decision_id
                or (
                    "human-review:"
                    f"{uuid4()}"
                ),
                field_name=(
                    "review_decision_id"
                ),
            )
        )

        proposal_snapshot = (
            queue_item.to_dict()
        )

        fingerprint_payload = {
            "review_decision_id":
                resolved_decision_id,
            "queue_item_id":
                queue_item.queue_item_id,
            "proposal_id":
                queue_item.proposal_id,
            "record_hash":
                queue_item.record_hash,
            "reviewer_id":
                resolved_reviewer_id,
            "reviewer_name":
                resolved_reviewer_name,
            "decision":
                resolved_decision.value,
            "reason":
                resolved_reason,
            "reviewed_at":
                resolved_reviewed_at.isoformat(),
            "proposal_snapshot":
                proposal_snapshot,
            "queue_priority_score":
                queue_item.priority_score,
            "audit_id":
                resolved_audit_id,
            "audit_valid":
                True,
        }

        decision_fingerprint = (
            hashlib.sha256(
                _canonical_json(
                    fingerprint_payload
                ).encode("utf-8")
            ).hexdigest()
        )

        return (
            AutonomousProposalHumanReviewDecision(
                review_decision_id=(
                    resolved_decision_id
                ),
                queue_item_id=(
                    queue_item.queue_item_id
                ),
                proposal_id=(
                    queue_item.proposal_id
                ),
                record_hash=(
                    queue_item.record_hash
                ),
                reviewer_id=(
                    resolved_reviewer_id
                ),
                reviewer_name=(
                    resolved_reviewer_name
                ),
                decision=resolved_decision,
                reason=resolved_reason,
                reviewed_at=(
                    resolved_reviewed_at
                ),
                proposal_snapshot=(
                    proposal_snapshot
                ),
                queue_priority_score=(
                    queue_item.priority_score
                ),
                audit_id=(
                    resolved_audit_id
                ),
                audit_valid=True,
                decision_fingerprint=(
                    decision_fingerprint
                ),
            )
        )


def create_autonomous_proposal_human_review(
    *,
    queue_item: AutonomousProposalReviewQueueItem,
    reviewer_id: str,
    reviewer_name: str,
    decision: (
        AutonomousHumanReviewDecisionType
        | str
    ),
    reason: str,
    audit_id: str,
    audit_valid: bool,
    reviewed_at: datetime | None = None,
    review_decision_id: str | None = None,
) -> AutonomousProposalHumanReviewDecision:
    return (
        AutonomousProposalHumanReviewService
        .create_decision(
            queue_item=queue_item,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            decision=decision,
            reason=reason,
            audit_id=audit_id,
            audit_valid=audit_valid,
            reviewed_at=reviewed_at,
            review_decision_id=(
                review_decision_id
            ),
        )
    )
