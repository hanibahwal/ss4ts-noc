from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.autonomous_execution_authorization_binding import (
    AutonomousExecutionAuthorizationBinding,
)
from app.models.execution_authorization import (
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionAuthorization,
    ExecutionRiskClass,
)
from app.services.autonomous_authorization_intent_audit import (
    AutonomousAuthorizationIntentAuditReport,
)
from app.services.autonomous_authorization_intent_store import (
    AutonomousAuthorizationIntentRecord,
)


class AutonomousExecutionAuthorizationBindingError(
    RuntimeError
):
    """Execution authorization binding validation failed."""


class AutonomousExecutionAuthorizationBindingService:
    """
    Validate and bind one verified autonomous authorization intent
    record to one existing pending ExecutionAuthorization.

    This service does not create, persist, approve, reject, revoke,
    consume, or execute the ExecutionAuthorization. It performs
    validation and produces a non-executable immutable binding only.
    """

    @staticmethod
    def _validate_intent_record(
        record: AutonomousAuthorizationIntentRecord,
    ) -> None:
        if not isinstance(
            record,
            AutonomousAuthorizationIntentRecord,
        ):
            raise TypeError(
                "intent_record must be an "
                "AutonomousAuthorizationIntentRecord"
            )

        if not record.verify_hash():
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent record hash is invalid"
            )

        payload = record.intent_payload

        bindings = {
            "authorization_intent_id":
                record.authorization_intent_id,
            "authorization_request_id":
                record.authorization_request_id,
            "request_record_hash":
                record.request_record_hash,
            "request_fingerprint":
                record.request_fingerprint,
            "request_audit_id":
                record.request_audit_id,
            "authorization_candidate_id":
                record.authorization_candidate_id,
            "candidate_record_hash":
                record.candidate_record_hash,
            "candidate_fingerprint":
                record.candidate_fingerprint,
            "proposal_id":
                record.proposal_id,
            "proposal_record_hash":
                record.proposal_record_hash,
            "bridge_fingerprint":
                record.bridge_fingerprint,
        }

        for field, expected in bindings.items():
            if payload.get(
                field
            ) != expected:
                raise AutonomousExecutionAuthorizationBindingError(
                    "Authorization intent record binding "
                    f"is invalid: {field}"
                )

        if (
            payload.get(
                "request_audit_valid"
            )
            is not True
            or record.request_audit_valid
            is not True
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent request audit is invalid"
            )

        false_claims = (
            "execution_authorization_created",
            "authorization_approved",
            "authorization_token_created",
            "approval_claim_created",
            "execution_lease_created",
            "execution_allowed",
            "can_execute",
        )

        for field in false_claims:
            if payload.get(
                field
            ) is not False:
                raise AutonomousExecutionAuthorizationBindingError(
                    "Authorization intent contains an "
                    f"unsafe claim: {field}"
                )

        if record.execution_authorization_created:
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent already created an "
                "execution authorization"
            )

        if record.execution_allowed or record.can_execute:
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent unexpectedly allows execution"
            )

    @staticmethod
    def _validate_intent_audit(
        audit: AutonomousAuthorizationIntentAuditReport,
        record: AutonomousAuthorizationIntentRecord,
    ) -> None:
        if not isinstance(
            audit,
            AutonomousAuthorizationIntentAuditReport,
        ):
            raise TypeError(
                "intent_audit must be an "
                "AutonomousAuthorizationIntentAuditReport"
            )

        audit_components_valid = all(
            (
                audit.audit_valid,
                audit.record_hashes_valid,
                audit.hash_chain_valid,
                audit.bridge_fingerprints_valid,
                audit.request_bindings_valid,
                audit.request_audits_valid,
                audit.safety_claims_valid,
            )
        )

        if not audit_components_valid:
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent audit is invalid"
            )

        if (
            audit.record_count < 1
            or audit.verified_record_count
            != audit.record_count
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent audit did not verify "
                "all records"
            )

        if (
            audit.first_sequence_number is None
            or audit.last_sequence_number is None
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent audit sequence "
                "range is missing"
            )

        if not (
            audit.first_sequence_number
            <= record.sequence_number
            <= audit.last_sequence_number
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent record is outside "
                "the audited sequence range"
            )

        if audit.execution_authorization_created:
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent audit unexpectedly "
                "created an execution authorization"
            )

        if audit.execution_allowed or audit.can_execute:
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent audit unexpectedly "
                "allows execution"
            )

    @staticmethod
    def _validate_execution_authorization(
        authorization: ExecutionAuthorization,
        record: AutonomousAuthorizationIntentRecord,
        *,
        validated_at: datetime,
    ) -> None:
        if not isinstance(
            authorization,
            ExecutionAuthorization,
        ):
            raise TypeError(
                "execution_authorization must be an "
                "ExecutionAuthorization"
            )

        if (
            authorization.status
            is not AuthorizationStatus.PENDING
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization status must be pending"
            )

        if (
            authorization.decision
            is not AuthorizationDecision.REQUIRE_APPROVAL
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization decision must "
                "require approval"
            )

        if authorization.approver is not None:
            raise AutonomousExecutionAuthorizationBindingError(
                "Pending execution authorization must not "
                "have an approver"
            )

        if authorization.approved_at is not None:
            raise AutonomousExecutionAuthorizationBindingError(
                "Pending execution authorization must not "
                "have an approval timestamp"
            )

        if authorization.execution_allowed:
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization unexpectedly "
                "allows execution"
            )

        if authorization.consumed:
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization is already consumed"
            )

        if authorization.is_usable:
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization is unexpectedly usable"
            )

        if not authorization.requires_human_approval:
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization must require "
                "human approval"
            )

        if authorization.expires_at is None:
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization expiration is missing"
            )

        expires_at = authorization.expires_at

        if (
            expires_at.tzinfo is None
            or expires_at.utcoffset() is None
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization expiration must "
                "be timezone-aware"
            )

        if (
            expires_at.astimezone(
                timezone.utc
            )
            <= validated_at
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization is expired"
            )

        intent_payload = record.intent_payload

        try:
            intent_risk_class = ExecutionRiskClass(
                intent_payload.get(
                    "risk_class"
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise AutonomousExecutionAuthorizationBindingError(
                "Authorization intent risk class is invalid"
            ) from exc

        if (
            authorization.risk_class
            is not intent_risk_class
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization risk class "
                "does not match the intent"
            )

        policy_bindings = {
            "dry_run_required":
                intent_payload.get(
                    "dry_run_required"
                ),
            "rollback_required":
                intent_payload.get(
                    "rollback_required"
                ),
            "verification_required":
                intent_payload.get(
                    "verification_required"
                ),
        }

        for field, expected in (
            policy_bindings.items()
        ):
            if getattr(
                authorization,
                field,
            ) is not expected:
                raise AutonomousExecutionAuthorizationBindingError(
                    "Execution authorization policy "
                    f"does not match the intent: {field}"
                )

        metadata = authorization.metadata

        if not isinstance(
            metadata,
            dict,
        ):
            raise AutonomousExecutionAuthorizationBindingError(
                "Execution authorization metadata is invalid"
            )

        unsafe_metadata = (
            "execution_enabled",
            "network_io_performed",
            "device_command_executed",
        )

        for field in unsafe_metadata:
            if metadata.get(
                field,
                False,
            ) is not False:
                raise AutonomousExecutionAuthorizationBindingError(
                    "Execution authorization contains "
                    f"unsafe metadata: {field}"
                )

    @staticmethod
    def _build_binding(
        *,
        intent_record: AutonomousAuthorizationIntentRecord,
        intent_audit: AutonomousAuthorizationIntentAuditReport,
        execution_authorization: ExecutionAuthorization,
        binding_id: str,
        created_at: datetime,
    ) -> AutonomousExecutionAuthorizationBinding:
        values = {
            "binding_id":
                binding_id,
            "authorization_intent_id":
                intent_record.authorization_intent_id,
            "intent_record_hash":
                intent_record.record_hash,
            "intent_bridge_fingerprint":
                intent_record.bridge_fingerprint,
            "intent_audit_id":
                intent_audit.audit_id,
            "intent_audit_valid":
                intent_audit.audit_valid,
            "execution_authorization_id":
                execution_authorization.authorization_id,
            "plan_id":
                execution_authorization.plan_id,
            "decision_id":
                execution_authorization.decision_id,
            "risk_class":
                execution_authorization.risk_class,
            "authorization_status":
                execution_authorization.status,
            "authorization_decision":
                execution_authorization.decision,
            "created_at":
                created_at,
            "expires_at":
                execution_authorization.expires_at,
        }

        provisional = (
            AutonomousExecutionAuthorizationBinding.__new__(
                AutonomousExecutionAuthorizationBinding
            )
        )

        for field, value in values.items():
            object.__setattr__(
                provisional,
                field,
                value,
            )

        object.__setattr__(
            provisional,
            "binding_fingerprint",
            "",
        )

        fingerprint = (
            provisional.calculate_fingerprint()
        )

        return AutonomousExecutionAuthorizationBinding(
            **values,
            binding_fingerprint=fingerprint,
        )

    def validate_and_bind(
        self,
        *,
        intent_record: AutonomousAuthorizationIntentRecord,
        intent_audit: AutonomousAuthorizationIntentAuditReport,
        execution_authorization: ExecutionAuthorization,
        binding_id: str | None = None,
        created_at: datetime | None = None,
    ) -> AutonomousExecutionAuthorizationBinding:
        normalized_created_at = (
            created_at
            or datetime.now(
                timezone.utc
            )
        )

        if not isinstance(
            normalized_created_at,
            datetime,
        ):
            raise TypeError(
                "created_at must be a datetime"
            )

        if (
            normalized_created_at.tzinfo is None
            or normalized_created_at.utcoffset() is None
        ):
            raise ValueError(
                "created_at must be timezone-aware"
            )

        normalized_created_at = (
            normalized_created_at.astimezone(
                timezone.utc
            )
        )

        normalized_binding_id = (
            str(
                binding_id
            ).strip()
            if binding_id is not None
            else (
                "autonomous-execution-authorization-"
                f"binding:{uuid4()}"
            )
        )

        if not normalized_binding_id:
            raise ValueError(
                "binding_id must not be empty"
            )

        self._validate_intent_record(
            intent_record
        )

        self._validate_intent_audit(
            intent_audit,
            intent_record,
        )

        self._validate_execution_authorization(
            execution_authorization,
            intent_record,
            validated_at=normalized_created_at,
        )

        return self._build_binding(
            intent_record=intent_record,
            intent_audit=intent_audit,
            execution_authorization=(
                execution_authorization
            ),
            binding_id=normalized_binding_id,
            created_at=normalized_created_at,
        )


def validate_execution_authorization_binding(
    *,
    intent_record: AutonomousAuthorizationIntentRecord,
    intent_audit: AutonomousAuthorizationIntentAuditReport,
    execution_authorization: ExecutionAuthorization,
    binding_id: str | None = None,
    created_at: datetime | None = None,
) -> AutonomousExecutionAuthorizationBinding:
    return (
        AutonomousExecutionAuthorizationBindingService()
        .validate_and_bind(
            intent_record=intent_record,
            intent_audit=intent_audit,
            execution_authorization=(
                execution_authorization
            ),
            binding_id=binding_id,
            created_at=created_at,
        )
    )
