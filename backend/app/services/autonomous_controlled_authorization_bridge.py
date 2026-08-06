from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.autonomous_authorization_intent import (
    AutonomousAuthorizationIntent,
)
from app.models.execution_authorization import (
    ExecutionRiskClass,
)
from app.services.autonomous_authorization_request_audit import (
    AutonomousAuthorizationRequestAuditReport,
)
from app.services.autonomous_authorization_request_store import (
    AutonomousAuthorizationRequestRecord,
)


class AutonomousControlledAuthorizationBridgeError(
    RuntimeError
):
    """Controlled authorization bridge validation failed."""


class AutonomousControlledAuthorizationBridge:
    """
    Converts one verified authorization request record into a
    non-executable authorization intent.

    This bridge does not instantiate ExecutionAuthorization,
    write to ExecutionAuthorizationStore, approve authorization,
    create tokens or approval claims, acquire execution leases,
    simulate execution, access networks or devices, generate
    commands, or execute actions.
    """

    @staticmethod
    def _validate_audit(
        audit: AutonomousAuthorizationRequestAuditReport,
    ) -> None:
        if not isinstance(
            audit,
            AutonomousAuthorizationRequestAuditReport,
        ):
            raise TypeError(
                "request_audit must be an "
                "AutonomousAuthorizationRequestAuditReport"
            )

        if not audit.audit_valid:
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request audit is invalid"
            )

        if audit.can_execute:
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request audit unexpectedly "
                "allows execution"
            )

    @staticmethod
    def _validate_record(
        record: AutonomousAuthorizationRequestRecord,
    ) -> None:
        if not isinstance(
            record,
            AutonomousAuthorizationRequestRecord,
        ):
            raise TypeError(
                "request_record must be an "
                "AutonomousAuthorizationRequestRecord"
            )

        if not record.verify_hash():
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request record hash is invalid"
            )

        payload = record.request_payload

        bindings = {
            "authorization_request_id":
                record.authorization_request_id,
            "request_fingerprint":
                record.request_fingerprint,
            "authorization_candidate_id":
                record.authorization_candidate_id,
            "candidate_record_hash":
                record.candidate_record_hash,
            "candidate_fingerprint":
                record.candidate_fingerprint,
            "review_decision_id":
                record.review_decision_id,
            "review_record_hash":
                record.review_record_hash,
            "proposal_id":
                record.proposal_id,
            "proposal_record_hash":
                record.proposal_record_hash,
            "candidate_audit_id":
                record.candidate_audit_id,
            "candidate_audit_valid":
                record.candidate_audit_valid,
            "requester_id":
                record.requester_id,
            "requested_at":
                record.requested_at,
            "request_reason":
                record.request_reason,
            "risk_class":
                record.risk_class,
            "dry_run_required":
                record.dry_run_required,
            "rollback_required":
                record.rollback_required,
            "verification_required":
                record.verification_required,
        }

        for field, expected in (
            bindings.items()
        ):
            if payload.get(
                field
            ) != expected:
                raise AutonomousControlledAuthorizationBridgeError(
                    "Authorization request payload binding "
                    f"is invalid: {field}"
                )

        if (
            payload.get(
                "authorization_request_created"
            )
            is not True
        ):
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request creation claim is invalid"
            )

        if (
            record.candidate_audit_valid
            is not True
            or payload.get(
                "candidate_audit_valid"
            )
            is not True
        ):
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization candidate audit is invalid"
            )

        false_claims = (
            "authorization_created",
            "authorization_approved",
            "authorization_token_created",
            "execution_lease_created",
            "execution_allowed",
            "can_execute",
        )

        for field in false_claims:
            if payload.get(
                field
            ) is not False:
                raise AutonomousControlledAuthorizationBridgeError(
                    "Authorization request contains an "
                    f"unsafe claim: {field}"
                )

        if record.authorization_created:
            raise AutonomousControlledAuthorizationBridgeError(
                "Execution authorization was already created"
            )

        if record.execution_allowed:
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request allows execution"
            )

        if record.can_execute:
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request is executable"
            )

        safety = payload.get(
            "safety"
        )

        if not isinstance(
            safety,
            dict,
        ):
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request safety metadata is missing"
            )

        required_safety = {
            "controlled_authorization_request_only":
                True,
            "execution_authorization_created":
                False,
            "authorization_approved":
                False,
            "authorization_token_created":
                False,
            "approval_claim_created":
                False,
            "execution_lease_created":
                False,
            "execution_allowed":
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
        }

        for field, expected in (
            required_safety.items()
        ):
            if safety.get(
                field
            ) is not expected:
                raise AutonomousControlledAuthorizationBridgeError(
                    "Authorization request safety metadata "
                    f"is invalid: {field}"
                )

        try:
            risk_class = ExecutionRiskClass(
                record.risk_class
            )

        except ValueError as exc:
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request risk class is invalid"
            ) from exc

        if risk_class is ExecutionRiskClass.UNKNOWN:
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request risk class "
                "must not be unknown"
            )

    def create_intent(
        self,
        *,
        request_record: AutonomousAuthorizationRequestRecord,
        request_audit: AutonomousAuthorizationRequestAuditReport,
        authorization_intent_id: str | None = None,
        created_at: datetime | None = None,
    ) -> AutonomousAuthorizationIntent:
        self._validate_audit(
            request_audit
        )

        self._validate_record(
            request_record
        )

        if (
            request_audit.record_count
            < 1
        ):
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request audit contains no records"
            )

        if (
            request_audit.verified_record_count
            != request_audit.record_count
        ):
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request audit did not verify "
                "all records"
            )

        if (
            request_audit.first_sequence_number
            is None
            or request_audit.last_sequence_number
            is None
        ):
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request audit sequence "
                "range is missing"
            )

        if not (
            request_audit.first_sequence_number
            <= request_record.sequence_number
            <= request_audit.last_sequence_number
        ):
            raise AutonomousControlledAuthorizationBridgeError(
                "Authorization request record is outside "
                "the audited sequence range"
            )

        normalized_created_at = (
            created_at
            or datetime.now(
                timezone.utc
            )
        )

        normalized_intent_id = (
            str(
                authorization_intent_id
            ).strip()
            if authorization_intent_id
            is not None
            else (
                "autonomous-authorization-intent:"
                f"{uuid4()}"
            )
        )

        values = {
            "authorization_intent_id":
                normalized_intent_id,
            "authorization_request_id":
                request_record.authorization_request_id,
            "request_record_hash":
                request_record.record_hash,
            "request_fingerprint":
                request_record.request_fingerprint,
            "request_audit_id":
                request_audit.audit_id,
            "request_audit_valid":
                request_audit.audit_valid,
            "authorization_candidate_id":
                request_record.authorization_candidate_id,
            "candidate_record_hash":
                request_record.candidate_record_hash,
            "candidate_fingerprint":
                request_record.candidate_fingerprint,
            "proposal_id":
                request_record.proposal_id,
            "proposal_record_hash":
                request_record.proposal_record_hash,
            "requester_id":
                request_record.requester_id,
            "requested_at":
                request_record.requested_at,
            "request_reason":
                request_record.request_reason,
            "risk_class":
                ExecutionRiskClass(
                    request_record.risk_class
                ),
            "dry_run_required":
                request_record.dry_run_required,
            "rollback_required":
                request_record.rollback_required,
            "verification_required":
                request_record.verification_required,
            "created_at":
                normalized_created_at,
        }

        provisional = (
            AutonomousAuthorizationIntent.__new__(
                AutonomousAuthorizationIntent
            )
        )

        for field, value in (
            values.items()
        ):
            object.__setattr__(
                provisional,
                field,
                value,
            )

        object.__setattr__(
            provisional,
            "bridge_fingerprint",
            "",
        )

        bridge_fingerprint = (
            provisional.calculate_fingerprint()
        )

        return AutonomousAuthorizationIntent(
            **values,
            bridge_fingerprint=(
                bridge_fingerprint
            ),
        )


def create_autonomous_authorization_intent(
    *,
    request_record: AutonomousAuthorizationRequestRecord,
    request_audit: AutonomousAuthorizationRequestAuditReport,
    authorization_intent_id: str | None = None,
    created_at: datetime | None = None,
) -> AutonomousAuthorizationIntent:
    return (
        AutonomousControlledAuthorizationBridge()
        .create_intent(
            request_record=request_record,
            request_audit=request_audit,
            authorization_intent_id=(
                authorization_intent_id
            ),
            created_at=created_at,
        )
    )
