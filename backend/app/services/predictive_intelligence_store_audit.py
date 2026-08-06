from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.predictive_intelligence import (
    PredictiveIntelligence,
)
from app.services.predictive_intelligence_store import (
    GENESIS_RECORD_HASH,
    PredictiveIntelligenceRecord,
    PredictiveIntelligenceStore,
)


@dataclass(
    frozen=True,
    slots=True,
)
class PredictiveIntelligenceStoreAuditReport:
    audit_id: str
    audited_at: datetime

    record_count: int
    first_sequence_number: int | None
    last_sequence_number: int | None

    record_hashes_valid: bool
    hash_chain_valid: bool
    sequence_integrity_valid: bool

    prediction_fingerprints_valid: bool
    prediction_payloads_valid: bool
    validation_payloads_valid: bool

    duplicate_identities_valid: bool
    timestamp_consistency_valid: bool
    safety_claims_valid: bool

    issues: tuple[str, ...]

    @property
    def audit_valid(
        self,
    ) -> bool:
        return all(
            (
                self.record_hashes_valid,
                self.hash_chain_valid,
                self.sequence_integrity_valid,
                self.prediction_fingerprints_valid,
                self.prediction_payloads_valid,
                self.validation_payloads_valid,
                self.duplicate_identities_valid,
                self.timestamp_consistency_valid,
                self.safety_claims_valid,
                not self.issues,
            )
        )

    @property
    def incident_created(
        self,
    ) -> bool:
        return False

    @property
    def recommendation_created(
        self,
    ) -> bool:
        return False

    @property
    def decision_created(
        self,
    ) -> bool:
        return False

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
    ) -> dict[str, Any]:
        return {
            "audit_id":
                self.audit_id,
            "audited_at":
                self.audited_at.isoformat(),
            "record_count":
                self.record_count,
            "first_sequence_number":
                self.first_sequence_number,
            "last_sequence_number":
                self.last_sequence_number,
            "checks": {
                "record_hashes_valid":
                    self.record_hashes_valid,
                "hash_chain_valid":
                    self.hash_chain_valid,
                "sequence_integrity_valid":
                    self.sequence_integrity_valid,
                "prediction_fingerprints_valid":
                    self.prediction_fingerprints_valid,
                "prediction_payloads_valid":
                    self.prediction_payloads_valid,
                "validation_payloads_valid":
                    self.validation_payloads_valid,
                "duplicate_identities_valid":
                    self.duplicate_identities_valid,
                "timestamp_consistency_valid":
                    self.timestamp_consistency_valid,
                "safety_claims_valid":
                    self.safety_claims_valid,
            },
            "issues":
                list(
                    self.issues
                ),
            "audit_valid":
                self.audit_valid,
            "incident_created":
                False,
            "recommendation_created":
                False,
            "decision_created":
                False,
            "authorization_created":
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
                "predictive_store_audit_only":
                    True,
                "read_only_audit":
                    True,
                "store_mutated":
                    False,
                "incident_created":
                    False,
                "recommendation_created":
                    False,
                "decision_created":
                    False,
                "authorization_created":
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


class PredictiveIntelligenceStoreAuditVerifier:
    PROTECTED_IDENTITY_FIELDS = (
        "prediction_id",
        "prediction_fingerprint",
        "record_hash",
    )

    PREDICTION_PAYLOAD_BINDINGS = (
        "prediction_id",
        "prediction_fingerprint",
        "prediction_type",
        "subject_type",
        "subject_id",
        "observed_at",
        "prediction_window_start",
        "prediction_window_end",
        "current_state",
        "predicted_state",
        "current_value",
        "predicted_value",
        "unit",
        "confidence_percent",
        "probability_percent",
        "risk_class",
        "severity",
        "model_name",
        "model_version",
        "created_at",
    )

    UNSAFE_FALSE_FIELDS = (
        "incident_created",
        "recommendation_created",
        "decision_created",
        "authorization_created",
        "approval_claim_created",
        "execution_lease_created",
        "execution_allowed",
        "can_execute",
    )

    @staticmethod
    def _normalize_audited_at(
        audited_at: datetime | None,
    ) -> datetime:
        value = (
            audited_at
            or datetime.now(
                timezone.utc
            )
        )

        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                "audited_at must be a datetime"
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "audited_at must be timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(
                str(
                    value
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            return None

        return parsed.astimezone(
            timezone.utc
        )

    @staticmethod
    def _prediction_from_record(
        record: PredictiveIntelligenceRecord,
    ) -> PredictiveIntelligence:
        observed_at = (
            PredictiveIntelligenceStoreAuditVerifier
            ._parse_datetime(
                record.observed_at
            )
        )

        window_start = (
            PredictiveIntelligenceStoreAuditVerifier
            ._parse_datetime(
                record.prediction_window_start
            )
        )

        window_end = (
            PredictiveIntelligenceStoreAuditVerifier
            ._parse_datetime(
                record.prediction_window_end
            )
        )

        created_at = (
            PredictiveIntelligenceStoreAuditVerifier
            ._parse_datetime(
                record.created_at
            )
        )

        if (
            observed_at is None
            or window_start is None
            or window_end is None
            or created_at is None
        ):
            raise ValueError(
                "Prediction timestamps are invalid"
            )

        return PredictiveIntelligence(
            prediction_id=(
                record.prediction_id
            ),
            prediction_type=(
                record.prediction_type
            ),
            subject_type=(
                record.subject_type
            ),
            subject_id=(
                record.subject_id
            ),
            observed_at=observed_at,
            prediction_window_start=(
                window_start
            ),
            prediction_window_end=(
                window_end
            ),
            current_state=(
                record.current_state
            ),
            predicted_state=(
                record.predicted_state
            ),
            current_value=(
                record.current_value
            ),
            predicted_value=(
                record.predicted_value
            ),
            unit=(
                record.unit
            ),
            confidence_percent=(
                record.confidence_percent
            ),
            probability_percent=(
                record.probability_percent
            ),
            risk_class=(
                record.risk_class
            ),
            severity=(
                record.severity
            ),
            evidence=(
                record.evidence
            ),
            contributing_factors=(
                record.contributing_factors
            ),
            model_name=(
                record.model_name
            ),
            model_version=(
                record.model_version
            ),
            source_metric_ids=(
                record.source_metric_ids
            ),
            metadata=dict(
                record.metadata
            ),
            created_at=created_at,
            prediction_fingerprint=(
                record.prediction_fingerprint
            ),
        )

    def verify(
        self,
        *,
        store: PredictiveIntelligenceStore,
        audited_at: datetime | None = None,
    ) -> PredictiveIntelligenceStoreAuditReport:
        if not isinstance(
            store,
            PredictiveIntelligenceStore,
        ):
            raise TypeError(
                "store must be a "
                "PredictiveIntelligenceStore"
            )

        resolved_audited_at = (
            self._normalize_audited_at(
                audited_at
            )
        )

        records = store.list_records(
            limit=1_000_000
        )

        issues: list[str] = []

        record_hashes_valid = True
        hash_chain_valid = True
        sequence_integrity_valid = True

        prediction_fingerprints_valid = True
        prediction_payloads_valid = True
        validation_payloads_valid = True

        duplicate_identities_valid = True
        timestamp_consistency_valid = True
        safety_claims_valid = True

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        seen: dict[
            str,
            set[Any],
        ] = {
            field_name: set()
            for field_name
            in self.PROTECTED_IDENTITY_FIELDS
        }

        for record in records:
            sequence = (
                record.sequence_number
            )

            if sequence != expected_sequence:
                sequence_integrity_valid = False
                issues.append(
                    "Sequence integrity mismatch at "
                    f"record {sequence}: expected "
                    f"{expected_sequence}"
                )

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                hash_chain_valid = False
                issues.append(
                    "Previous record hash mismatch at "
                    f"sequence {sequence}"
                )

            if not record.verify_hash():
                record_hashes_valid = False
                issues.append(
                    "Record hash mismatch at "
                    f"sequence {sequence}"
                )

            prediction_payload = (
                record.prediction_payload
            )

            if not isinstance(
                prediction_payload,
                dict,
            ):
                prediction_payloads_valid = False
                issues.append(
                    "Prediction payload is invalid at "
                    f"sequence {sequence}"
                )
                prediction_payload = {}

            for field_name in (
                self.PREDICTION_PAYLOAD_BINDINGS
            ):
                expected_value = getattr(
                    record,
                    field_name,
                )

                if (
                    prediction_payload.get(
                        field_name
                    )
                    != expected_value
                ):
                    prediction_payloads_valid = False
                    issues.append(
                        "Prediction payload binding "
                        f"mismatch for {field_name} at "
                        f"sequence {sequence}"
                    )

            if (
                prediction_payload.get(
                    "evidence"
                )
                != list(
                    record.evidence
                )
            ):
                prediction_payloads_valid = False
                issues.append(
                    "Prediction evidence binding "
                    f"mismatch at sequence {sequence}"
                )

            if (
                prediction_payload.get(
                    "contributing_factors"
                )
                != list(
                    record.contributing_factors
                )
            ):
                prediction_payloads_valid = False
                issues.append(
                    "Prediction contributing factors "
                    f"mismatch at sequence {sequence}"
                )

            if (
                prediction_payload.get(
                    "source_metric_ids"
                )
                != list(
                    record.source_metric_ids
                )
            ):
                prediction_payloads_valid = False
                issues.append(
                    "Prediction source metrics mismatch "
                    f"at sequence {sequence}"
                )

            if (
                prediction_payload.get(
                    "metadata"
                )
                != record.metadata
            ):
                prediction_payloads_valid = False
                issues.append(
                    "Prediction metadata mismatch at "
                    f"sequence {sequence}"
                )

            try:
                reconstructed = (
                    self._prediction_from_record(
                        record
                    )
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                prediction_fingerprints_valid = False
                issues.append(
                    "Prediction reconstruction failed "
                    f"at sequence {sequence}: {exc}"
                )

            else:
                if (
                    reconstructed
                    .prediction_fingerprint
                    != record
                    .prediction_fingerprint
                    or
                    reconstructed
                    .calculate_fingerprint()
                    != record
                    .prediction_fingerprint
                ):
                    prediction_fingerprints_valid = False
                    issues.append(
                        "Prediction fingerprint mismatch "
                        f"at sequence {sequence}"
                    )

            validation_payload = (
                record.validation_payload
            )

            if not isinstance(
                validation_payload,
                dict,
            ):
                validation_payloads_valid = False
                issues.append(
                    "Validation payload is invalid at "
                    f"sequence {sequence}"
                )
                validation_payload = {}

            validation_checks = (
                validation_payload.get(
                    "checks"
                )
            )

            if not isinstance(
                validation_checks,
                dict,
            ):
                validation_payloads_valid = False
                issues.append(
                    "Validation checks are invalid at "
                    f"sequence {sequence}"
                )
                validation_checks = {}

            if (
                record.validation_valid
                is not True
                or validation_payload.get(
                    "validation_valid"
                )
                is not True
                or validation_payload.get(
                    "prediction_accepted"
                )
                is not True
                or validation_payload.get(
                    "prediction_id"
                )
                != record.prediction_id
                or validation_payload.get(
                    "validation_errors"
                )
                != []
            ):
                validation_payloads_valid = False
                issues.append(
                    "Validation payload binding failed "
                    f"at sequence {sequence}"
                )

            required_validation_checks = (
                "fingerprint_valid",
                "prediction_window_valid",
                "subject_compatible",
                "state_transition_valid",
                "metric_direction_valid",
                "probability_confidence_valid",
                "risk_severity_valid",
                "evidence_sufficient",
                "model_identity_valid",
                "temporal_consistency_valid",
            )

            for check_name in (
                required_validation_checks
            ):
                if (
                    validation_checks.get(
                        check_name
                    )
                    is not True
                ):
                    validation_payloads_valid = False
                    issues.append(
                        "Validation check failed for "
                        f"{check_name} at sequence "
                        f"{sequence}"
                    )

            observed_at = self._parse_datetime(
                record.observed_at
            )

            window_start = self._parse_datetime(
                record.prediction_window_start
            )

            window_end = self._parse_datetime(
                record.prediction_window_end
            )

            created_at = self._parse_datetime(
                record.created_at
            )

            stored_at = self._parse_datetime(
                record.stored_at
            )

            if (
                observed_at is None
                or window_start is None
                or window_end is None
                or created_at is None
                or stored_at is None
                or window_start < observed_at
                or window_end <= window_start
                or created_at < observed_at
                or stored_at < created_at
                or resolved_audited_at < stored_at
            ):
                timestamp_consistency_valid = False
                issues.append(
                    "Prediction timestamp consistency "
                    f"failed at sequence {sequence}"
                )

            for field_name in (
                self.PROTECTED_IDENTITY_FIELDS
            ):
                value = getattr(
                    record,
                    field_name,
                )

                if value in seen[
                    field_name
                ]:
                    duplicate_identities_valid = False
                    issues.append(
                        "Duplicate protected identity "
                        f"{field_name} at sequence "
                        f"{sequence}"
                    )

                seen[
                    field_name
                ].add(
                    value
                )

            for payload_name, payload in (
                (
                    "prediction",
                    prediction_payload,
                ),
                (
                    "validation",
                    validation_payload,
                ),
            ):
                for field_name in (
                    self.UNSAFE_FALSE_FIELDS
                ):
                    if (
                        payload.get(
                            field_name
                        )
                        is not False
                    ):
                        safety_claims_valid = False
                        issues.append(
                            f"Unsafe {payload_name} claim "
                            f"{field_name} at sequence "
                            f"{sequence}"
                        )

            if (
                record.incident_created
                or record.recommendation_created
                or record.decision_created
                or record.authorization_created
                or record.approval_claim_created
                or record.execution_lease_created
                or record.execution_allowed
                or record.can_execute
            ):
                safety_claims_valid = False
                issues.append(
                    "Stored prediction unexpectedly "
                    "grants execution authority at "
                    f"sequence {sequence}"
                )

            expected_sequence += 1
            expected_previous_hash = (
                record.record_hash
            )

        return PredictiveIntelligenceStoreAuditReport(
            audit_id=(
                "predictive-store-audit:"
                f"{uuid4()}"
            ),
            audited_at=resolved_audited_at,
            record_count=len(
                records
            ),
            first_sequence_number=(
                records[0].sequence_number
                if records
                else None
            ),
            last_sequence_number=(
                records[-1].sequence_number
                if records
                else None
            ),
            record_hashes_valid=(
                record_hashes_valid
            ),
            hash_chain_valid=(
                hash_chain_valid
            ),
            sequence_integrity_valid=(
                sequence_integrity_valid
            ),
            prediction_fingerprints_valid=(
                prediction_fingerprints_valid
            ),
            prediction_payloads_valid=(
                prediction_payloads_valid
            ),
            validation_payloads_valid=(
                validation_payloads_valid
            ),
            duplicate_identities_valid=(
                duplicate_identities_valid
            ),
            timestamp_consistency_valid=(
                timestamp_consistency_valid
            ),
            safety_claims_valid=(
                safety_claims_valid
            ),
            issues=tuple(
                issues
            ),
        )


def verify_predictive_intelligence_store(
    store: PredictiveIntelligenceStore,
    *,
    audited_at: datetime | None = None,
) -> PredictiveIntelligenceStoreAuditReport:
    return (
        PredictiveIntelligenceStoreAuditVerifier()
        .verify(
            store=store,
            audited_at=audited_at,
        )
    )
