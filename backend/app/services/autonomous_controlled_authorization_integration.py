from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.models.autonomous_authorization_intent import (
    AutonomousAuthorizationIntent,
)
from app.models.autonomous_authorization_request import (
    AutonomousControlledAuthorizationRequest,
)
from app.services.autonomous_authorization_intent_audit import (
    AutonomousAuthorizationIntentAuditReport,
    verify_autonomous_authorization_intent_store,
)
from app.services.autonomous_authorization_intent_store import (
    AutonomousAuthorizationIntentRecord,
    AutonomousAuthorizationIntentStore,
)
from app.services.autonomous_authorization_request_audit import (
    AutonomousAuthorizationRequestAuditReport,
    verify_autonomous_authorization_request_store,
)
from app.services.autonomous_authorization_request_store import (
    AutonomousAuthorizationRequestRecord,
    AutonomousAuthorizationRequestStore,
)
from app.services.autonomous_controlled_authorization_bridge import (
    create_autonomous_authorization_intent,
)


class AutonomousControlledAuthorizationIntegrationError(
    RuntimeError
):
    """Controlled authorization integration failed."""


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousControlledAuthorizationIntegrationResult:
    integration_id: str
    integrated_at: datetime

    request_record: AutonomousAuthorizationRequestRecord
    request_audit: AutonomousAuthorizationRequestAuditReport

    authorization_intent: AutonomousAuthorizationIntent
    intent_record: AutonomousAuthorizationIntentRecord
    intent_audit: AutonomousAuthorizationIntentAuditReport

    integration_valid: bool

    @property
    def execution_authorization_created(
        self,
    ) -> bool:
        return False

    @property
    def authorization_approved(
        self,
    ) -> bool:
        return False

    @property
    def authorization_token_created(
        self,
    ) -> bool:
        return False

    @property
    def approval_claim_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_lease_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_allowed(
        self,
    ) -> bool:
        return False

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict:
        return {
            "integration_id":
                self.integration_id,
            "integrated_at":
                self.integrated_at.isoformat(),
            "request_record":
                self.request_record.to_dict(),
            "request_audit":
                self.request_audit.to_dict(),
            "authorization_intent":
                self.authorization_intent.to_dict(),
            "intent_record":
                self.intent_record.to_dict(),
            "intent_audit":
                self.intent_audit.to_dict(),
            "integration_valid":
                self.integration_valid,
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
            "can_execute":
                False,
            "safety": {
                "controlled_authorization_integration_only":
                    True,
                "request_store_append_only":
                    True,
                "intent_store_append_only":
                    True,
                "execution_authorization_created":
                    False,
                "execution_authorization_stored":
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
            },
        }


class AutonomousControlledAuthorizationIntegration:
    """
    Final non-executable controlled-authorization integration.

    Flow:
        request
        -> immutable request store
        -> request store audit
        -> non-executable authorization intent
        -> immutable intent store
        -> intent store audit

    This service does not create or store ExecutionAuthorization,
    approve authorization, create tokens or claims, acquire leases,
    start simulations, access networks or devices, generate
    commands, or execute actions.
    """

    def __init__(
        self,
        *,
        request_store: AutonomousAuthorizationRequestStore,
        intent_store: AutonomousAuthorizationIntentStore,
    ) -> None:
        if not isinstance(
            request_store,
            AutonomousAuthorizationRequestStore,
        ):
            raise TypeError(
                "request_store must be an "
                "AutonomousAuthorizationRequestStore"
            )

        if not isinstance(
            intent_store,
            AutonomousAuthorizationIntentStore,
        ):
            raise TypeError(
                "intent_store must be an "
                "AutonomousAuthorizationIntentStore"
            )

        self.request_store = request_store
        self.intent_store = intent_store

    @staticmethod
    def _validate_request_record(
        record: AutonomousAuthorizationRequestRecord,
    ) -> None:
        if not record.verify_hash():
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request record hash is invalid"
            )

        if record.authorization_created:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request unexpectedly created "
                "an execution authorization"
            )

        if record.execution_allowed:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request unexpectedly allows execution"
            )

        if record.can_execute:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request is unexpectedly executable"
            )

    @staticmethod
    def _validate_request_audit(
        audit: AutonomousAuthorizationRequestAuditReport,
        record: AutonomousAuthorizationRequestRecord,
    ) -> None:
        if not audit.audit_valid:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request store audit is invalid"
            )

        if (
            audit.record_count < 1
            or audit.verified_record_count
            != audit.record_count
        ):
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request store audit did not "
                "verify all records"
            )

        if (
            audit.first_sequence_number is None
            or audit.last_sequence_number is None
        ):
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request audit sequence "
                "range is missing"
            )

        if not (
            audit.first_sequence_number
            <= record.sequence_number
            <= audit.last_sequence_number
        ):
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request record is outside "
                "the audited sequence range"
            )

        if audit.can_execute:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization request audit unexpectedly "
                "allows execution"
            )

    @staticmethod
    def _validate_intent(
        intent: AutonomousAuthorizationIntent,
        request_record: AutonomousAuthorizationRequestRecord,
        request_audit: AutonomousAuthorizationRequestAuditReport,
    ) -> None:
        if (
            intent.calculate_fingerprint()
            != intent.bridge_fingerprint
        ):
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent fingerprint is invalid"
            )

        bindings = {
            "authorization_request_id":
                request_record.authorization_request_id,
            "request_record_hash":
                request_record.record_hash,
            "request_fingerprint":
                request_record.request_fingerprint,
            "request_audit_id":
                request_audit.audit_id,
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
        }

        for field, expected in bindings.items():
            if getattr(
                intent,
                field,
            ) != expected:
                raise AutonomousControlledAuthorizationIntegrationError(
                    "Authorization intent binding mismatch: "
                    f"{field}"
                )

        if intent.request_audit_valid is not True:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent request audit binding "
                "is invalid"
            )

        if intent.execution_authorization_created:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent unexpectedly created "
                "an execution authorization"
            )

        if intent.authorization_approved:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent unexpectedly approved "
                "authorization"
            )

        if intent.authorization_token_created:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent unexpectedly created a token"
            )

        if intent.approval_claim_created:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent unexpectedly created "
                "an approval claim"
            )

        if intent.execution_lease_created:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent unexpectedly created "
                "an execution lease"
            )

        if intent.execution_allowed or intent.can_execute:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent unexpectedly allows execution"
            )

    @staticmethod
    def _validate_intent_record(
        record: AutonomousAuthorizationIntentRecord,
        intent: AutonomousAuthorizationIntent,
    ) -> None:
        if not record.verify_hash():
            raise AutonomousControlledAuthorizationIntegrationError(
                "Stored authorization intent record hash is invalid"
            )

        bindings = {
            "authorization_intent_id":
                intent.authorization_intent_id,
            "bridge_fingerprint":
                intent.bridge_fingerprint,
            "authorization_request_id":
                intent.authorization_request_id,
            "request_record_hash":
                intent.request_record_hash,
            "request_fingerprint":
                intent.request_fingerprint,
            "request_audit_id":
                intent.request_audit_id,
            "authorization_candidate_id":
                intent.authorization_candidate_id,
            "candidate_record_hash":
                intent.candidate_record_hash,
            "candidate_fingerprint":
                intent.candidate_fingerprint,
            "proposal_id":
                intent.proposal_id,
            "proposal_record_hash":
                intent.proposal_record_hash,
        }

        for field, expected in bindings.items():
            if getattr(
                record,
                field,
            ) != expected:
                raise AutonomousControlledAuthorizationIntegrationError(
                    "Stored authorization intent binding "
                    f"mismatch: {field}"
                )

        if record.execution_authorization_created:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Stored authorization intent unexpectedly "
                "created an execution authorization"
            )

        if record.execution_allowed or record.can_execute:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Stored authorization intent unexpectedly "
                "allows execution"
            )

    @staticmethod
    def _validate_intent_audit(
        audit: AutonomousAuthorizationIntentAuditReport,
        record: AutonomousAuthorizationIntentRecord,
    ) -> None:
        if not audit.audit_valid:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent store audit is invalid"
            )

        if (
            audit.record_count < 1
            or audit.verified_record_count
            != audit.record_count
        ):
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent store audit did not "
                "verify all records"
            )

        if (
            audit.first_sequence_number is None
            or audit.last_sequence_number is None
        ):
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent audit sequence "
                "range is missing"
            )

        if not (
            audit.first_sequence_number
            <= record.sequence_number
            <= audit.last_sequence_number
        ):
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent record is outside "
                "the audited sequence range"
            )

        if audit.execution_authorization_created:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent audit unexpectedly "
                "created an execution authorization"
            )

        if audit.execution_allowed or audit.can_execute:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Authorization intent audit unexpectedly "
                "allows execution"
            )

    def integrate(
        self,
        *,
        request: AutonomousControlledAuthorizationRequest,
        integration_id: str | None = None,
        authorization_intent_id: str | None = None,
        integrated_at: datetime | None = None,
    ) -> AutonomousControlledAuthorizationIntegrationResult:
        if not isinstance(
            request,
            AutonomousControlledAuthorizationRequest,
        ):
            raise TypeError(
                "request must be an "
                "AutonomousControlledAuthorizationRequest"
            )

        normalized_integration_id = (
            str(
                integration_id
            ).strip()
            if integration_id is not None
            else (
                "autonomous-controlled-authorization-"
                f"integration:{uuid4()}"
            )
        )

        if not normalized_integration_id:
            raise ValueError(
                "integration_id must not be empty"
            )

        normalized_integrated_at = (
            integrated_at
            or datetime.now(
                timezone.utc
            )
        )

        request_record = self.request_store.append(
            request=request
        )

        self._validate_request_record(
            request_record
        )

        request_audit = (
            verify_autonomous_authorization_request_store(
                self.request_store
            )
        )

        self._validate_request_audit(
            request_audit,
            request_record,
        )

        authorization_intent = (
            create_autonomous_authorization_intent(
                request_record=request_record,
                request_audit=request_audit,
                authorization_intent_id=(
                    authorization_intent_id
                ),
                created_at=(
                    normalized_integrated_at
                ),
            )
        )

        self._validate_intent(
            authorization_intent,
            request_record,
            request_audit,
        )

        intent_record = self.intent_store.append(
            intent=authorization_intent
        )

        self._validate_intent_record(
            intent_record,
            authorization_intent,
        )

        intent_audit = (
            verify_autonomous_authorization_intent_store(
                self.intent_store
            )
        )

        self._validate_intent_audit(
            intent_audit,
            intent_record,
        )

        integration_valid = all(
            (
                request_record.verify_hash(),
                request_audit.audit_valid,
                authorization_intent.calculate_fingerprint()
                == authorization_intent.bridge_fingerprint,
                intent_record.verify_hash(),
                intent_audit.audit_valid,
                request_record.authorization_request_id
                == authorization_intent.authorization_request_id,
                request_record.record_hash
                == authorization_intent.request_record_hash,
                request_audit.audit_id
                == authorization_intent.request_audit_id,
                authorization_intent.authorization_intent_id
                == intent_record.authorization_intent_id,
                authorization_intent.bridge_fingerprint
                == intent_record.bridge_fingerprint,
            )
        )

        if not integration_valid:
            raise AutonomousControlledAuthorizationIntegrationError(
                "Controlled authorization integration "
                "verification failed"
            )

        return (
            AutonomousControlledAuthorizationIntegrationResult(
                integration_id=normalized_integration_id,
                integrated_at=normalized_integrated_at,
                request_record=request_record,
                request_audit=request_audit,
                authorization_intent=authorization_intent,
                intent_record=intent_record,
                intent_audit=intent_audit,
                integration_valid=True,
            )
        )


def integrate_controlled_authorization(
    *,
    request: AutonomousControlledAuthorizationRequest,
    request_store: AutonomousAuthorizationRequestStore,
    intent_store: AutonomousAuthorizationIntentStore,
    integration_id: str | None = None,
    authorization_intent_id: str | None = None,
    integrated_at: datetime | None = None,
) -> AutonomousControlledAuthorizationIntegrationResult:
    return (
        AutonomousControlledAuthorizationIntegration(
            request_store=request_store,
            intent_store=intent_store,
        ).integrate(
            request=request,
            integration_id=integration_id,
            authorization_intent_id=(
                authorization_intent_id
            ),
            integrated_at=integrated_at,
        )
    )
