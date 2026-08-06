from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


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


def _required_text(
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


def _normalized_datetime(
    value: datetime,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "created_at must be a datetime"
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
class AutonomousAuthorizationReviewCandidate:
    authorization_candidate_id: str

    review_decision_id: str
    review_record_hash: str
    decision_fingerprint: str

    proposal_id: str
    proposal_record_hash: str
    queue_item_id: str

    reviewer_id: str
    human_decision: str

    review_audit_id: str
    review_audit_valid: bool

    created_at: datetime

    candidate_fingerprint: str

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "authorization_candidate_id",
            "review_decision_id",
            "review_record_hash",
            "decision_fingerprint",
            "proposal_id",
            "proposal_record_hash",
            "queue_item_id",
            "reviewer_id",
            "human_decision",
            "review_audit_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        if self.review_audit_valid is not True:
            raise ValueError(
                "Authorization candidate requires "
                "a valid human review store audit"
            )

        object.__setattr__(
            self,
            "created_at",
            _normalized_datetime(
                self.created_at
            ),
        )

        if (
            self.human_decision
            != (
                "approved_for_"
                "authorization_review"
            )
        ):
            raise ValueError(
                "Human decision is not eligible "
                "for authorization review"
            )

        expected = (
            self.calculate_fingerprint()
        )

        if (
            self.candidate_fingerprint
            != expected
        ):
            raise ValueError(
                "Authorization candidate "
                "fingerprint mismatch"
            )

    @property
    def eligible_for_authorization_review(
        self,
    ) -> bool:
        return True

    @property
    def authorization_created(
        self,
    ) -> bool:
        return False

    @property
    def approval_claim_created(
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
            "authorization_candidate_id":
                self.authorization_candidate_id,
            "review_decision_id":
                self.review_decision_id,
            "review_record_hash":
                self.review_record_hash,
            "decision_fingerprint":
                self.decision_fingerprint,
            "proposal_id":
                self.proposal_id,
            "proposal_record_hash":
                self.proposal_record_hash,
            "queue_item_id":
                self.queue_item_id,
            "reviewer_id":
                self.reviewer_id,
            "human_decision":
                self.human_decision,
            "review_audit_id":
                self.review_audit_id,
            "review_audit_valid":
                self.review_audit_valid,
            "created_at":
                self.created_at.isoformat(),
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
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "eligible_for_authorization_review":
                True,
            "authorization_created":
                False,
            "approval_claim_created":
                False,
            "can_execute":
                False,
            "safety": {
                "authorization_candidate_only":
                    True,
                "authorization_token_created":
                    False,
                "authorization_created":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
                    False,
                "execution_approved":
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
            },
        }
