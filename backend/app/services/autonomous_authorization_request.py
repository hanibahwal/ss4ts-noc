from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from uuid import uuid4

from app.models.autonomous_authorization_request import (
    AutonomousControlledAuthorizationRequest,
    normalize_execution_risk_class,
)
from app.models.execution_authorization import (
    ExecutionRiskClass,
)
from app.services.autonomous_authorization_candidate_audit import (
    AutonomousAuthorizationCandidateAuditReport,
    _calculate_candidate_fingerprint,
)
from app.services.autonomous_authorization_candidate_store import (
    AutonomousAuthorizationCandidateRecord,
)


SERVICE_NAME = (
    "SS4TS Autonomous Controlled "
    "Authorization Request"
)

SERVICE_VERSION = "1.0.0"

APPROVED_HUMAN_DECISION = (
    "approved_for_authorization_review"
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


def _normalize_requested_at(
    value: datetime | None,
) -> datetime:
    resolved = (
        value
        or datetime.now(
            timezone.utc
        )
    )

    if not isinstance(
        resolved,
        datetime,
    ):
        raise TypeError(
            "requested_at must be a datetime"
        )

    if resolved.tzinfo is None:
        resolved = resolved.replace(
            tzinfo=timezone.utc
        )

    return resolved.astimezone(
        timezone.utc
    )


class AutonomousControlledAuthorizationRequestService:
    """
    Produce a controlled authorization request contract only.

    This service does not instantiate ExecutionAuthorization,
    write to ExecutionAuthorizationStore, approve authorization,
    create a token or claim, acquire an execution lease,
    simulate an operation, access a network or device, or execute.
    """

    @staticmethod
    def create_request(
        *,
        candidate_record: (
            AutonomousAuthorizationCandidateRecord
        ),
        candidate_audit: (
            AutonomousAuthorizationCandidateAuditReport
        ),
        requester_id: str,
        request_reason: str,
        risk_class: ExecutionRiskClass | str,
        dry_run_required: bool = True,
        rollback_required: bool = True,
        verification_required: bool = True,
        requested_at: datetime | None = None,
        authorization_request_id: (
            str | None
        ) = None,
    ) -> AutonomousControlledAuthorizationRequest:
        if not isinstance(
            candidate_record,
            AutonomousAuthorizationCandidateRecord,
        ):
            raise TypeError(
                "candidate_record must be an "
                "AutonomousAuthorizationCandidateRecord"
            )

        if not isinstance(
            candidate_audit,
            AutonomousAuthorizationCandidateAuditReport,
        ):
            raise TypeError(
                "candidate_audit must be an "
                "AutonomousAuthorizationCandidateAuditReport"
            )

        if not candidate_record.verify_hash():
            raise ValueError(
                "Authorization candidate record "
                "hash is invalid"
            )

        if candidate_record.can_execute:
            raise ValueError(
                "Executable authorization candidates "
                "are not accepted"
            )

        if candidate_audit.audit_valid is not True:
            raise ValueError(
                "A valid authorization candidate "
                "store audit is required"
            )

        if candidate_audit.can_execute:
            raise ValueError(
                "Executable candidate audits "
                "are not accepted"
            )

        if (
            candidate_audit.record_count
            < 1
            or candidate_audit
            .verified_record_count
            < 1
        ):
            raise ValueError(
                "Candidate audit contains no "
                "verified records"
            )

        payload = (
            candidate_record.candidate_payload
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "Authorization candidate payload "
                "must be a dictionary"
            )

        calculated_candidate_fingerprint = (
            _calculate_candidate_fingerprint(
                payload
            )
        )

        if (
            calculated_candidate_fingerprint
            != candidate_record
            .candidate_fingerprint
            or payload.get(
                "candidate_fingerprint"
            )
            != candidate_record
            .candidate_fingerprint
        ):
            raise ValueError(
                "Authorization candidate "
                "fingerprint is invalid"
            )

        bindings = {
            "authorization_candidate_id":
                candidate_record
                .authorization_candidate_id,
            "candidate_fingerprint":
                candidate_record
                .candidate_fingerprint,
            "review_decision_id":
                candidate_record
                .review_decision_id,
            "review_record_hash":
                candidate_record
                .review_record_hash,
            "decision_fingerprint":
                candidate_record
                .decision_fingerprint,
            "proposal_id":
                candidate_record
                .proposal_id,
            "proposal_record_hash":
                candidate_record
                .proposal_record_hash,
            "queue_item_id":
                candidate_record
                .queue_item_id,
            "reviewer_id":
                candidate_record
                .reviewer_id,
            "human_decision":
                candidate_record
                .human_decision,
            "review_audit_id":
                candidate_record
                .review_audit_id,
        }

        for field, expected_value in (
            bindings.items()
        ):
            if (
                payload.get(
                    field
                )
                != expected_value
            ):
                raise ValueError(
                    "Authorization candidate payload "
                    f"binding mismatch: {field}"
                )

        if (
            candidate_record.human_decision
            != APPROVED_HUMAN_DECISION
            or payload.get(
                "human_decision"
            )
            != APPROVED_HUMAN_DECISION
        ):
            raise ValueError(
                "Authorization candidate human "
                "decision is not approved for "
                "authorization review"
            )

        if (
            payload.get(
                "review_audit_valid"
            )
            is not True
        ):
            raise ValueError(
                "Authorization candidate review "
                "audit is not valid"
            )

        if (
            payload.get(
                "eligible_for_authorization_review"
            )
            is not True
        ):
            raise ValueError(
                "Candidate is not eligible for "
                "authorization review"
            )

        if (
            payload.get(
                "authorization_created"
            )
            is not False
        ):
            raise ValueError(
                "Authorization candidate already "
                "claims an authorization"
            )

        if (
            payload.get(
                "approval_claim_created"
            )
            is not False
        ):
            raise ValueError(
                "Authorization candidate already "
                "claims an approval"
            )

        if (
            payload.get(
                "can_execute"
            )
            is not False
        ):
            raise ValueError(
                "Authorization candidate permits "
                "execution"
            )

        safety = payload.get(
            "safety"
        )

        if not isinstance(
            safety,
            dict,
        ):
            raise ValueError(
                "Authorization candidate safety "
                "metadata is missing"
            )

        forbidden_safety_claims = (
            "authorization_token_created",
            "authorization_created",
            "approval_claim_created",
            "execution_lease_created",
            "execution_approved",
            "simulation_started",
            "network_io_performed",
            "device_access_performed",
            "command_generated",
            "device_command_executed",
        )

        for field in forbidden_safety_claims:
            if safety.get(
                field
            ) is not False:
                raise ValueError(
                    "Authorization candidate safety "
                    f"contract failed: {field}"
                )

        if (
            safety.get(
                "authorization_candidate_only"
            )
            is not True
        ):
            raise ValueError(
                "Candidate safety metadata does not "
                "identify a candidate-only record"
            )

        normalized_requester = _required_text(
            requester_id,
            field_name="requester_id",
        )

        normalized_reason = _required_text(
            request_reason,
            field_name="request_reason",
        )

        normalized_risk = (
            normalize_execution_risk_class(
                risk_class
            )
        )

        for field_name, value in (
            (
                "dry_run_required",
                dry_run_required,
            ),
            (
                "rollback_required",
                rollback_required,
            ),
            (
                "verification_required",
                verification_required,
            ),
        ):
            if not isinstance(
                value,
                bool,
            ):
                raise TypeError(
                    f"{field_name} must be a bool"
                )

        resolved_request_id = _required_text(
            authorization_request_id
            or (
                "autonomous-authorization-request:"
                f"{uuid4()}"
            ),
            field_name=(
                "authorization_request_id"
            ),
        )

        resolved_requested_at = (
            _normalize_requested_at(
                requested_at
            )
        )

        fingerprint_payload = {
            "authorization_request_id":
                resolved_request_id,
            "authorization_candidate_id":
                candidate_record
                .authorization_candidate_id,
            "candidate_record_hash":
                candidate_record.record_hash,
            "candidate_fingerprint":
                candidate_record
                .candidate_fingerprint,
            "review_decision_id":
                candidate_record
                .review_decision_id,
            "review_record_hash":
                candidate_record
                .review_record_hash,
            "proposal_id":
                candidate_record.proposal_id,
            "proposal_record_hash":
                candidate_record
                .proposal_record_hash,
            "candidate_audit_id":
                candidate_audit.audit_id,
            "candidate_audit_valid":
                True,
            "requester_id":
                normalized_requester,
            "requested_at":
                resolved_requested_at
                .isoformat(),
            "request_reason":
                normalized_reason,
            "risk_class":
                normalized_risk.value,
            "dry_run_required":
                dry_run_required,
            "rollback_required":
                rollback_required,
            "verification_required":
                verification_required,
        }

        request_fingerprint = hashlib.sha256(
            _canonical_json(
                fingerprint_payload
            ).encode("utf-8")
        ).hexdigest()

        return AutonomousControlledAuthorizationRequest(
            authorization_request_id=(
                resolved_request_id
            ),
            authorization_candidate_id=(
                candidate_record
                .authorization_candidate_id
            ),
            candidate_record_hash=(
                candidate_record.record_hash
            ),
            candidate_fingerprint=(
                candidate_record
                .candidate_fingerprint
            ),
            review_decision_id=(
                candidate_record
                .review_decision_id
            ),
            review_record_hash=(
                candidate_record
                .review_record_hash
            ),
            proposal_id=(
                candidate_record.proposal_id
            ),
            proposal_record_hash=(
                candidate_record
                .proposal_record_hash
            ),
            candidate_audit_id=(
                candidate_audit.audit_id
            ),
            candidate_audit_valid=True,
            requester_id=(
                normalized_requester
            ),
            requested_at=(
                resolved_requested_at
            ),
            request_reason=(
                normalized_reason
            ),
            risk_class=(
                normalized_risk
            ),
            dry_run_required=(
                dry_run_required
            ),
            rollback_required=(
                rollback_required
            ),
            verification_required=(
                verification_required
            ),
            request_fingerprint=(
                request_fingerprint
            ),
        )


def create_autonomous_authorization_request(
    *,
    candidate_record: (
        AutonomousAuthorizationCandidateRecord
    ),
    candidate_audit: (
        AutonomousAuthorizationCandidateAuditReport
    ),
    requester_id: str,
    request_reason: str,
    risk_class: ExecutionRiskClass | str,
    dry_run_required: bool = True,
    rollback_required: bool = True,
    verification_required: bool = True,
    requested_at: datetime | None = None,
    authorization_request_id: str | None = None,
) -> AutonomousControlledAuthorizationRequest:
    return (
        AutonomousControlledAuthorizationRequestService
        .create_request(
            candidate_record=candidate_record,
            candidate_audit=candidate_audit,
            requester_id=requester_id,
            request_reason=request_reason,
            risk_class=risk_class,
            dry_run_required=(
                dry_run_required
            ),
            rollback_required=(
                rollback_required
            ),
            verification_required=(
                verification_required
            ),
            requested_at=requested_at,
            authorization_request_id=(
                authorization_request_id
            ),
        )
    )
