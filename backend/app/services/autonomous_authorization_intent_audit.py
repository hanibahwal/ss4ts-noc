from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.services.autonomous_authorization_intent_store import (
    GENESIS_RECORD_HASH,
    AutonomousAuthorizationIntentIntegrityError,
    AutonomousAuthorizationIntentStore,
)


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousAuthorizationIntentAuditReport:
    audit_id: str
    audited_at: datetime

    record_count: int
    verified_record_count: int

    first_sequence_number: int | None
    last_sequence_number: int | None

    record_hashes_valid: bool
    hash_chain_valid: bool
    bridge_fingerprints_valid: bool
    request_bindings_valid: bool
    request_audits_valid: bool
    safety_claims_valid: bool

    audit_valid: bool

    @property
    def execution_authorization_created(
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
            "audit_id": self.audit_id,
            "audited_at": self.audited_at.isoformat(),
            "record_count": self.record_count,
            "verified_record_count":
                self.verified_record_count,
            "first_sequence_number":
                self.first_sequence_number,
            "last_sequence_number":
                self.last_sequence_number,
            "record_hashes_valid":
                self.record_hashes_valid,
            "hash_chain_valid":
                self.hash_chain_valid,
            "bridge_fingerprints_valid":
                self.bridge_fingerprints_valid,
            "request_bindings_valid":
                self.request_bindings_valid,
            "request_audits_valid":
                self.request_audits_valid,
            "safety_claims_valid":
                self.safety_claims_valid,
            "audit_valid":
                self.audit_valid,
            "execution_authorization_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "safety": {
                "authorization_intent_audit_only": True,
                "intent_store_read_only": True,
                "execution_authorization_created": False,
                "execution_authorization_stored": False,
                "authorization_approved": False,
                "authorization_token_created": False,
                "approval_claim_created": False,
                "execution_lease_created": False,
                "execution_allowed": False,
                "execution_approved": False,
                "simulation_started": False,
                "network_io_performed": False,
                "device_access_performed": False,
                "command_generated": False,
                "device_command_executed": False,
            },
        }


def verify_autonomous_authorization_intent_store(
    store: AutonomousAuthorizationIntentStore,
    *,
    audit_id: str | None = None,
    audited_at: datetime | None = None,
) -> AutonomousAuthorizationIntentAuditReport:
    if not isinstance(
        store,
        AutonomousAuthorizationIntentStore,
    ):
        raise TypeError(
            "store must be an "
            "AutonomousAuthorizationIntentStore"
        )

    normalized_audit_id = (
        str(
            audit_id
        ).strip()
        if audit_id is not None
        else (
            "autonomous-authorization-intent-audit:"
            f"{uuid4()}"
        )
    )

    if not normalized_audit_id:
        raise ValueError(
            "audit_id must not be empty"
        )

    normalized_audited_at = (
        audited_at
        or datetime.now(
            timezone.utc
        )
    )

    records = []

    record_hashes_valid = True
    hash_chain_valid = True
    bridge_fingerprints_valid = True
    request_bindings_valid = True
    request_audits_valid = True
    safety_claims_valid = True

    try:
        records = store.list_records(
            limit=1000
        )

    except AutonomousAuthorizationIntentIntegrityError:
        record_hashes_valid = False
        hash_chain_valid = False
        bridge_fingerprints_valid = False
        request_bindings_valid = False
        request_audits_valid = False
        safety_claims_valid = False

    verified_record_count = 0

    expected_sequence = 1
    expected_previous_hash = (
        GENESIS_RECORD_HASH
    )

    for record in records:
        record_valid = True

        if not record.verify_hash():
            record_hashes_valid = False
            record_valid = False

        if (
            record.sequence_number
            != expected_sequence
        ):
            hash_chain_valid = False
            record_valid = False

        if (
            record.previous_record_hash
            != expected_previous_hash
        ):
            hash_chain_valid = False
            record_valid = False

        payload = record.intent_payload

        if (
            payload.get(
                "bridge_fingerprint"
            )
            != record.bridge_fingerprint
        ):
            bridge_fingerprints_valid = False
            record_valid = False

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
        }

        for field, expected in bindings.items():
            if payload.get(field) != expected:
                request_bindings_valid = False
                record_valid = False

        if (
            record.request_audit_valid
            is not True
            or payload.get(
                "request_audit_valid"
            )
            is not True
        ):
            request_audits_valid = False
            record_valid = False

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
            if payload.get(field) is not False:
                safety_claims_valid = False
                record_valid = False

        safety = payload.get(
            "safety"
        )

        required_safety = {
            "authorization_intent_only": True,
            "request_store_read_only": True,
            "execution_authorization_created": False,
            "execution_authorization_stored": False,
            "authorization_approved": False,
            "authorization_token_created": False,
            "approval_claim_created": False,
            "execution_lease_created": False,
            "execution_allowed": False,
            "execution_approved": False,
            "simulation_started": False,
            "network_io_performed": False,
            "device_access_performed": False,
            "command_generated": False,
            "device_command_executed": False,
        }

        if not isinstance(
            safety,
            dict,
        ):
            safety_claims_valid = False
            record_valid = False

        else:
            for field, expected in (
                required_safety.items()
            ):
                if safety.get(field) is not expected:
                    safety_claims_valid = False
                    record_valid = False

        if record.can_execute:
            safety_claims_valid = False
            record_valid = False

        if record.execution_allowed:
            safety_claims_valid = False
            record_valid = False

        if record.execution_authorization_created:
            safety_claims_valid = False
            record_valid = False

        if record_valid:
            verified_record_count += 1

        expected_previous_hash = (
            record.record_hash
        )

        expected_sequence += 1

    record_count = len(
        records
    )

    first_sequence_number = (
        records[0].sequence_number
        if records
        else None
    )

    last_sequence_number = (
        records[-1].sequence_number
        if records
        else None
    )

    audit_valid = all(
        (
            record_hashes_valid,
            hash_chain_valid,
            bridge_fingerprints_valid,
            request_bindings_valid,
            request_audits_valid,
            safety_claims_valid,
            verified_record_count
            == record_count,
        )
    )

    return AutonomousAuthorizationIntentAuditReport(
        audit_id=normalized_audit_id,
        audited_at=normalized_audited_at,
        record_count=record_count,
        verified_record_count=(
            verified_record_count
        ),
        first_sequence_number=(
            first_sequence_number
        ),
        last_sequence_number=(
            last_sequence_number
        ),
        record_hashes_valid=(
            record_hashes_valid
        ),
        hash_chain_valid=(
            hash_chain_valid
        ),
        bridge_fingerprints_valid=(
            bridge_fingerprints_valid
        ),
        request_bindings_valid=(
            request_bindings_valid
        ),
        request_audits_valid=(
            request_audits_valid
        ),
        safety_claims_valid=(
            safety_claims_valid
        ),
        audit_valid=audit_valid,
    )
