from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any


class AutonomousHumanReviewDecisionType(
    str,
    Enum,
):
    APPROVED_FOR_AUTHORIZATION_REVIEW = (
        "approved_for_authorization_review"
    )

    REJECTED = "rejected"

    CHANGES_REQUESTED = (
        "changes_requested"
    )


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


def _normalize_datetime(
    value: datetime,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "reviewed_at must be a datetime"
        )

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousProposalHumanReviewDecision:
    review_decision_id: str

    queue_item_id: str
    proposal_id: str
    record_hash: str

    reviewer_id: str
    reviewer_name: str

    decision: (
        AutonomousHumanReviewDecisionType
    )

    reason: str
    reviewed_at: datetime

    proposal_snapshot: dict[str, Any]

    queue_priority_score: float

    audit_id: str
    audit_valid: bool

    decision_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "review_decision_id",
            _normalize_required_text(
                self.review_decision_id,
                field_name=(
                    "review_decision_id"
                ),
            ),
        )

        object.__setattr__(
            self,
            "queue_item_id",
            _normalize_required_text(
                self.queue_item_id,
                field_name="queue_item_id",
            ),
        )

        object.__setattr__(
            self,
            "proposal_id",
            _normalize_required_text(
                self.proposal_id,
                field_name="proposal_id",
            ),
        )

        object.__setattr__(
            self,
            "record_hash",
            _normalize_required_text(
                self.record_hash,
                field_name="record_hash",
            ),
        )

        object.__setattr__(
            self,
            "reviewer_id",
            _normalize_required_text(
                self.reviewer_id,
                field_name="reviewer_id",
            ),
        )

        object.__setattr__(
            self,
            "reviewer_name",
            _normalize_required_text(
                self.reviewer_name,
                field_name="reviewer_name",
            ),
        )

        object.__setattr__(
            self,
            "reason",
            _normalize_required_text(
                self.reason,
                field_name="reason",
            ),
        )

        if not isinstance(
            self.decision,
            AutonomousHumanReviewDecisionType,
        ):
            try:
                normalized_decision = (
                    AutonomousHumanReviewDecisionType(
                        str(
                            self.decision
                        ).strip()
                    )
                )

            except ValueError as exc:
                raise ValueError(
                    "Unsupported human review "
                    "decision"
                ) from exc

            object.__setattr__(
                self,
                "decision",
                normalized_decision,
            )

        object.__setattr__(
            self,
            "reviewed_at",
            _normalize_datetime(
                self.reviewed_at
            ),
        )

        if not isinstance(
            self.proposal_snapshot,
            dict,
        ):
            raise TypeError(
                "proposal_snapshot must be a "
                "dictionary"
            )

        object.__setattr__(
            self,
            "proposal_snapshot",
            dict(
                self.proposal_snapshot
            ),
        )

        priority = float(
            self.queue_priority_score
        )

        if priority < 0:
            raise ValueError(
                "queue_priority_score must "
                "not be negative"
            )

        object.__setattr__(
            self,
            "queue_priority_score",
            priority,
        )

        object.__setattr__(
            self,
            "audit_id",
            _normalize_required_text(
                self.audit_id,
                field_name="audit_id",
            ),
        )

        if self.audit_valid is not True:
            raise ValueError(
                "Human review decision requires "
                "a valid proposal audit"
            )

        expected_fingerprint = (
            self.calculate_fingerprint()
        )

        if (
            self.decision_fingerprint
            != expected_fingerprint
        ):
            raise ValueError(
                "Human review decision "
                "fingerprint mismatch"
            )

    @property
    def approved_for_authorization_review(
        self,
    ) -> bool:
        return (
            self.decision
            is AutonomousHumanReviewDecisionType
            .APPROVED_FOR_AUTHORIZATION_REVIEW
        )

    @property
    def requires_controlled_authorization(
        self,
    ) -> bool:
        return (
            self.approved_for_authorization_review
        )

    @property
    def authorization_created(
        self,
    ) -> bool:
        return False

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def fingerprint_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "review_decision_id":
                self.review_decision_id,
            "queue_item_id":
                self.queue_item_id,
            "proposal_id":
                self.proposal_id,
            "record_hash":
                self.record_hash,
            "reviewer_id":
                self.reviewer_id,
            "reviewer_name":
                self.reviewer_name,
            "decision":
                self.decision.value,
            "reason":
                self.reason,
            "reviewed_at":
                self.reviewed_at.isoformat(),
            "proposal_snapshot":
                self.proposal_snapshot,
            "queue_priority_score":
                self.queue_priority_score,
            "audit_id":
                self.audit_id,
            "audit_valid":
                self.audit_valid,
        }

    def calculate_fingerprint(
        self,
    ) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.fingerprint_payload()
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            **self.fingerprint_payload(),
            "decision_fingerprint":
                self.decision_fingerprint,
            "approved_for_authorization_review":
                (
                    self
                    .approved_for_authorization_review
                ),
            "requires_controlled_authorization":
                (
                    self
                    .requires_controlled_authorization
                ),
            "authorization_created":
                False,
            "can_execute":
                False,
            "safety": {
                "human_originated_decision":
                    True,
                "automatic_approval":
                    False,
                "immutable_proposal_modified":
                    False,
                "approval_claim_created":
                    False,
                "authorization_created":
                    False,
                "execution_approved":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        }
