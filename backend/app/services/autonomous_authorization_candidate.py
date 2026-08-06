from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from app.models.autonomous_authorization_candidate import (
    AutonomousAuthorizationReviewCandidate,
)
from app.services.autonomous_proposal_review_audit import (
    AutonomousProposalReviewAuditReport,
)
from app.services.autonomous_proposal_review_store import (
    AutonomousProposalReviewRecord,
)


SERVICE_NAME = (
    "SS4TS Autonomous Authorization "
    "Review Candidate"
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


def _normalize_created_at(
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
            "created_at must be a datetime"
        )

    if resolved.tzinfo is None:
        resolved = resolved.replace(
            tzinfo=timezone.utc
        )

    return resolved.astimezone(
        timezone.utc
    )


class AutonomousAuthorizationCandidateService:
    """
    Create a non-executable authorization review candidate.

    This service does not create an ExecutionAuthorization,
    approval claim, authorization token, execution lease,
    simulation, network connection, device command, or execution.
    """

    @staticmethod
    def create_candidate(
        *,
        review_record: (
            AutonomousProposalReviewRecord
        ),
        review_audit: (
            AutonomousProposalReviewAuditReport
        ),
        created_at: datetime | None = None,
        authorization_candidate_id: (
            str | None
        ) = None,
    ) -> AutonomousAuthorizationReviewCandidate:
        if not isinstance(
            review_record,
            AutonomousProposalReviewRecord,
        ):
            raise TypeError(
                "review_record must be an "
                "AutonomousProposalReviewRecord"
            )

        if not isinstance(
            review_audit,
            AutonomousProposalReviewAuditReport,
        ):
            raise TypeError(
                "review_audit must be an "
                "AutonomousProposalReviewAuditReport"
            )

        if not review_record.verify_hash():
            raise ValueError(
                "Human review record hash "
                "is invalid"
            )

        if review_record.can_execute:
            raise ValueError(
                "Executable human review records "
                "are not accepted"
            )

        if review_audit.audit_valid is not True:
            raise ValueError(
                "A valid human review store "
                "audit is required"
            )

        if (
            review_audit.record_hashes_valid
            is not True
        ):
            raise ValueError(
                "Human review record hashes "
                "are not valid"
            )

        if (
            review_audit
            .decision_fingerprints_valid
            is not True
        ):
            raise ValueError(
                "Human review decision "
                "fingerprints are not valid"
            )

        if (
            review_audit.payload_bindings_valid
            is not True
        ):
            raise ValueError(
                "Human review payload bindings "
                "are not valid"
            )

        if (
            review_audit.decision_types_valid
            is not True
        ):
            raise ValueError(
                "Human review decision types "
                "are not valid"
            )

        payload = (
            review_record.decision_payload
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "Human review decision payload "
                "must be a dictionary"
            )

        if (
            review_record.decision
            != (
                "approved_for_"
                "authorization_review"
            )
        ):
            raise ValueError(
                "Only decisions approved for "
                "authorization review may "
                "become candidates"
            )

        bindings = {
            "review_decision_id": (
                review_record
                .review_decision_id
            ),
            "decision_fingerprint": (
                review_record
                .decision_fingerprint
            ),
            "queue_item_id": (
                review_record.queue_item_id
            ),
            "proposal_id": (
                review_record.proposal_id
            ),
            "record_hash": (
                review_record
                .proposal_record_hash
            ),
            "reviewer_id": (
                review_record.reviewer_id
            ),
            "decision": (
                review_record.decision
            ),
        }

        for field, expected in (
            bindings.items()
        ):
            if (
                payload.get(field)
                != expected
            ):
                raise ValueError(
                    "Human review payload "
                    f"binding mismatch: {field}"
                )

        if (
            payload.get(
                "audit_valid"
            )
            is not True
        ):
            raise ValueError(
                "Human review payload does not "
                "contain a valid proposal audit"
            )

        if (
            payload.get(
                "authorization_created"
            )
            is not False
        ):
            raise ValueError(
                "Human review payload already "
                "claims an authorization"
            )

        if (
            payload.get(
                "can_execute"
            )
            is not False
        ):
            raise ValueError(
                "Human review payload must not "
                "allow execution"
            )

        resolved_id = _required_text(
            authorization_candidate_id
            or (
                "authorization-candidate:"
                f"{uuid4()}"
            ),
            field_name=(
                "authorization_candidate_id"
            ),
        )

        resolved_created_at = (
            _normalize_created_at(
                created_at
            )
        )

        fingerprint_payload = {
            "authorization_candidate_id":
                resolved_id,
            "review_decision_id":
                review_record
                .review_decision_id,
            "review_record_hash":
                review_record.record_hash,
            "decision_fingerprint":
                review_record
                .decision_fingerprint,
            "proposal_id":
                review_record.proposal_id,
            "proposal_record_hash":
                review_record
                .proposal_record_hash,
            "queue_item_id":
                review_record.queue_item_id,
            "reviewer_id":
                review_record.reviewer_id,
            "human_decision":
                review_record.decision,
            "review_audit_id":
                review_audit.audit_id,
            "review_audit_valid":
                True,
            "created_at":
                resolved_created_at
                .isoformat(),
        }

        candidate_fingerprint = (
            hashlib.sha256(
                _canonical_json(
                    fingerprint_payload
                ).encode("utf-8")
            ).hexdigest()
        )

        return (
            AutonomousAuthorizationReviewCandidate(
                authorization_candidate_id=(
                    resolved_id
                ),
                review_decision_id=(
                    review_record
                    .review_decision_id
                ),
                review_record_hash=(
                    review_record.record_hash
                ),
                decision_fingerprint=(
                    review_record
                    .decision_fingerprint
                ),
                proposal_id=(
                    review_record.proposal_id
                ),
                proposal_record_hash=(
                    review_record
                    .proposal_record_hash
                ),
                queue_item_id=(
                    review_record.queue_item_id
                ),
                reviewer_id=(
                    review_record.reviewer_id
                ),
                human_decision=(
                    review_record.decision
                ),
                review_audit_id=(
                    review_audit.audit_id
                ),
                review_audit_valid=True,
                created_at=(
                    resolved_created_at
                ),
                candidate_fingerprint=(
                    candidate_fingerprint
                ),
            )
        )


def create_autonomous_authorization_candidate(
    *,
    review_record: AutonomousProposalReviewRecord,
    review_audit: (
        AutonomousProposalReviewAuditReport
    ),
    created_at: datetime | None = None,
    authorization_candidate_id: str | None = None,
) -> AutonomousAuthorizationReviewCandidate:
    return (
        AutonomousAuthorizationCandidateService
        .create_candidate(
            review_record=review_record,
            review_audit=review_audit,
            created_at=created_at,
            authorization_candidate_id=(
                authorization_candidate_id
            ),
        )
    )
