from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from app.services.executive_predictive_report_store import (
    GENESIS_RECORD_HASH,
    ExecutivePredictiveReportRecord,
    ExecutivePredictiveReportStore,
)


AUDIT_SERVICE_NAME = (
    "SS4TS Executive Predictive Report Store Audit"
)

AUDIT_SERVICE_VERSION = "1.0.0"


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _normalize_datetime(
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
            "audited_at must be a datetime"
        )

    if (
        resolved.tzinfo is None
        or resolved.utcoffset() is None
    ):
        raise ValueError(
            "audited_at must be timezone-aware"
        )

    return resolved.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ExecutivePredictiveReportStoreAuditReport:
    audit_id: str
    audit_valid: bool

    record_count: int
    first_sequence_number: int | None
    last_sequence_number: int | None

    first_record_hash: str | None
    last_record_hash: str | None

    checks: dict[str, bool]
    audit_errors: tuple[str, ...]
    audit_warnings: tuple[str, ...]

    audited_at: datetime
    auditor_name: str
    auditor_version: str

    @property
    def report_created(
        self,
    ) -> bool:
        return False

    @property
    def pdf_rendered(
        self,
    ) -> bool:
        return False

    @property
    def incident_created(
        self,
    ) -> bool:
        return False

    @property
    def recommendation_executed(
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
            "audit_valid":
                self.audit_valid,
            "record_count":
                self.record_count,
            "first_sequence_number":
                self.first_sequence_number,
            "last_sequence_number":
                self.last_sequence_number,
            "first_record_hash":
                self.first_record_hash,
            "last_record_hash":
                self.last_record_hash,
            "checks":
                dict(
                    self.checks
                ),
            "audit_errors":
                list(
                    self.audit_errors
                ),
            "audit_warnings":
                list(
                    self.audit_warnings
                ),
            "audited_at":
                self.audited_at.isoformat(),
            "auditor_name":
                self.auditor_name,
            "auditor_version":
                self.auditor_version,
            "report_created":
                False,
            "pdf_rendered":
                False,
            "incident_created":
                False,
            "recommendation_executed":
                False,
            "decision_created":
                False,
            "authorization_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "safety": {
                "audit_only":
                    True,
                "read_only":
                    True,
                "store_mutated":
                    False,
                "report_created":
                    False,
                "pdf_rendered":
                    False,
                "incident_created":
                    False,
                "recommendation_executed":
                    False,
                "decision_created":
                    False,
                "authorization_created":
                    False,
                "execution_allowed":
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


class ExecutivePredictiveReportStoreAuditor:
    REQUIRED_CHECKS = (
        "store_chain_valid",
        "sequence_numbers_valid",
        "previous_hash_links_valid",
        "record_hashes_valid",
        "report_identity_bindings_valid",
        "validation_bindings_valid",
        "source_audit_bindings_valid",
        "timestamp_order_valid",
        "payload_safety_valid",
        "record_safety_valid",
    )

    @staticmethod
    def _payload_safety_valid(
        payload: dict[str, Any],
    ) -> bool:
        return all(
            (
                payload.get(
                    "incident_created"
                )
                is False,
                payload.get(
                    "recommendation_executed"
                )
                is False,
                payload.get(
                    "decision_created"
                )
                is False,
                payload.get(
                    "authorization_created"
                )
                is False,
                payload.get(
                    "execution_allowed"
                )
                is False,
                payload.get(
                    "can_execute"
                )
                is False,
            )
        )

    @staticmethod
    def _record_timestamp_valid(
        record: ExecutivePredictiveReportRecord,
        audited_at: datetime,
    ) -> bool:
        try:
            generated_at = datetime.fromisoformat(
                record.generated_at
            )

            stored_at = datetime.fromisoformat(
                record.stored_at
            )

        except (
            TypeError,
            ValueError,
        ):
            return False

        if (
            generated_at.tzinfo is None
            or generated_at.utcoffset() is None
            or stored_at.tzinfo is None
            or stored_at.utcoffset() is None
        ):
            return False

        return (
            stored_at.astimezone(
                timezone.utc
            )
            >= generated_at.astimezone(
                timezone.utc
            )
            and audited_at
            >= stored_at.astimezone(
                timezone.utc
            )
        )

    @staticmethod
    def _audit_id(
        *,
        record_count: int,
        first_record_hash: str | None,
        last_record_hash: str | None,
        audited_at: datetime,
    ) -> str:
        payload = {
            "record_count":
                record_count,
            "first_record_hash":
                first_record_hash,
            "last_record_hash":
                last_record_hash,
            "audited_at":
                audited_at.isoformat(),
            "auditor_name":
                AUDIT_SERVICE_NAME,
            "auditor_version":
                AUDIT_SERVICE_VERSION,
        }

        digest = hashlib.sha256(
            _canonical_json(
                payload
            ).encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            "executive-predictive-report-store-audit:"
            f"{digest}"
        )

    def verify(
        self,
        *,
        store: ExecutivePredictiveReportStore,
        audited_at: datetime | None = None,
    ) -> ExecutivePredictiveReportStoreAuditReport:
        if not isinstance(
            store,
            ExecutivePredictiveReportStore,
        ):
            raise TypeError(
                "store must be an "
                "ExecutivePredictiveReportStore"
            )

        resolved_audited_at = (
            _normalize_datetime(
                audited_at
            )
        )

        records = store.list_records(
            limit=1_000_000
        )

        checks: dict[str, bool] = {
            check_name: True
            for check_name
            in self.REQUIRED_CHECKS
        }

        errors: list[str] = []
        warnings: list[str] = []

        checks["store_chain_valid"] = (
            store.verify_chain()
        )

        if not records:
            warnings.append(
                "Executive predictive report "
                "store is empty"
            )

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        for record in records:
            if (
                record.sequence_number
                != expected_sequence
            ):
                checks[
                    "sequence_numbers_valid"
                ] = False

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                checks[
                    "previous_hash_links_valid"
                ] = False

            if not record.verify_hash():
                checks[
                    "record_hashes_valid"
                ] = False

            report_payload = (
                record.report_payload
            )

            validation_payload = (
                record.validation_payload
            )

            if not all(
                (
                    report_payload.get(
                        "report_id"
                    )
                    == record.report_id,
                    report_payload.get(
                        "report_fingerprint"
                    )
                    == record.report_fingerprint,
                    report_payload.get(
                        "report_type"
                    )
                    == record.report_type,
                )
            ):
                checks[
                    "report_identity_bindings_valid"
                ] = False

            if not all(
                (
                    record.validation_valid,
                    validation_payload.get(
                        "validation_valid"
                    )
                    is True,
                    validation_payload.get(
                        "report_accepted"
                    )
                    is True,
                    validation_payload.get(
                        "report_id"
                    )
                    == record.report_id,
                    validation_payload.get(
                        "report_fingerprint"
                    )
                    == record.report_fingerprint,
                )
            ):
                checks[
                    "validation_bindings_valid"
                ] = False

            if not all(
                (
                    record.source_audit_valid,
                    report_payload.get(
                        "source_audit_valid"
                    )
                    is True,
                    report_payload.get(
                        "source_audit_id"
                    )
                    == record.source_audit_id,
                )
            ):
                checks[
                    "source_audit_bindings_valid"
                ] = False

            if not self._record_timestamp_valid(
                record,
                resolved_audited_at,
            ):
                checks[
                    "timestamp_order_valid"
                ] = False

            if not all(
                (
                    self._payload_safety_valid(
                        report_payload
                    ),
                    self._payload_safety_valid(
                        validation_payload
                    ),
                )
            ):
                checks[
                    "payload_safety_valid"
                ] = False

            record_payload = (
                record.to_dict()
            )

            if not self._payload_safety_valid(
                record_payload
            ):
                checks[
                    "record_safety_valid"
                ] = False

            expected_sequence += 1
            expected_previous_hash = (
                record.record_hash
            )

        for check_name in self.REQUIRED_CHECKS:
            if not checks.get(
                check_name,
                False,
            ):
                errors.append(
                    f"{check_name} failed"
                )

        audit_valid = (
            not errors
            and all(
                checks.get(
                    check_name,
                    False,
                )
                for check_name
                in self.REQUIRED_CHECKS
            )
        )

        first_record = (
            records[0]
            if records
            else None
        )

        last_record = (
            records[-1]
            if records
            else None
        )

        audit_id = self._audit_id(
            record_count=len(
                records
            ),
            first_record_hash=(
                first_record.record_hash
                if first_record
                else None
            ),
            last_record_hash=(
                last_record.record_hash
                if last_record
                else None
            ),
            audited_at=(
                resolved_audited_at
            ),
        )

        return (
            ExecutivePredictiveReportStoreAuditReport(
                audit_id=(
                    audit_id
                ),
                audit_valid=(
                    audit_valid
                ),
                record_count=len(
                    records
                ),
                first_sequence_number=(
                    first_record.sequence_number
                    if first_record
                    else None
                ),
                last_sequence_number=(
                    last_record.sequence_number
                    if last_record
                    else None
                ),
                first_record_hash=(
                    first_record.record_hash
                    if first_record
                    else None
                ),
                last_record_hash=(
                    last_record.record_hash
                    if last_record
                    else None
                ),
                checks=checks,
                audit_errors=tuple(
                    errors
                ),
                audit_warnings=tuple(
                    warnings
                ),
                audited_at=(
                    resolved_audited_at
                ),
                auditor_name=(
                    AUDIT_SERVICE_NAME
                ),
                auditor_version=(
                    AUDIT_SERVICE_VERSION
                ),
            )
        )


def verify_executive_predictive_report_store(
    *,
    store: ExecutivePredictiveReportStore,
    audited_at: datetime | None = None,
) -> ExecutivePredictiveReportStoreAuditReport:
    return (
        ExecutivePredictiveReportStoreAuditor()
        .verify(
            store=store,
            audited_at=audited_at,
        )
    )
