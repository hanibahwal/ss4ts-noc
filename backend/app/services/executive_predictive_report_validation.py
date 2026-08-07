from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.executive_predictive_report import (
    ExecutivePredictiveOutlook,
    ExecutivePredictiveReport,
    ExecutivePredictiveRiskClass,
)
from app.services.executive_predictive_report_builder import (
    RISK_RANK,
    SERVICE_NAME,
)
from app.services.predictive_intelligence_store import (
    PredictiveIntelligenceRecord,
    PredictiveIntelligenceStore,
)
from app.services.predictive_intelligence_store_audit import (
    PredictiveIntelligenceStoreAuditReport,
)


VALIDATION_SERVICE_NAME = (
    "SS4TS Executive Predictive Report Validator"
)

VALIDATION_SERVICE_VERSION = "1.0.0"


@dataclass(
    frozen=True,
    slots=True,
)
class ExecutivePredictiveReportValidationResult:
    report_id: str
    report_fingerprint: str

    validation_valid: bool
    report_accepted: bool

    validation_errors: tuple[str, ...]
    checks: dict[str, bool]

    validated_at: datetime
    validator_name: str
    validator_version: str

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
            "report_id":
                self.report_id,
            "report_fingerprint":
                self.report_fingerprint,
            "validation_valid":
                self.validation_valid,
            "report_accepted":
                self.report_accepted,
            "validation_errors":
                list(
                    self.validation_errors
                ),
            "checks":
                dict(
                    self.checks
                ),
            "validated_at":
                self.validated_at.isoformat(),
            "validator_name":
                self.validator_name,
            "validator_version":
                self.validator_version,
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
                "report_validation_only":
                    True,
                "read_only_validation":
                    True,
                "report_mutated":
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


class ExecutivePredictiveReportValidator:
    REQUIRED_CHECKS = (
        "fingerprint_valid",
        "source_audit_valid",
        "source_record_count_valid",
        "source_prediction_bindings_valid",
        "source_record_hashes_valid",
        "report_period_valid",
        "generated_at_valid",
        "prediction_counts_valid",
        "risk_class_valid",
        "service_outlook_valid",
        "health_score_valid",
        "required_content_valid",
        "builder_identity_valid",
        "schema_version_valid",
        "safety_claims_valid",
    )

    @staticmethod
    def _normalize_validated_at(
        validated_at: datetime | None,
    ) -> datetime:
        value = (
            validated_at
            or datetime.now(
                timezone.utc
            )
        )

        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                "validated_at must be a datetime"
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "validated_at must be timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )

    @staticmethod
    def _record_datetime(
        record: PredictiveIntelligenceRecord,
        field_name: str,
    ) -> datetime:
        value = getattr(
            record,
            field_name,
        )

        try:
            parsed = datetime.fromisoformat(
                str(
                    value
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} is invalid"
            ) from exc

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            raise ValueError(
                f"{field_name} must be timezone-aware"
            )

        return parsed.astimezone(
            timezone.utc
        )

    @staticmethod
    def _expected_risk(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> ExecutivePredictiveRiskClass:
        if not records:
            return (
                ExecutivePredictiveRiskClass.LOW
            )

        highest = max(
            records,
            key=lambda record: (
                RISK_RANK.get(
                    record.risk_class,
                    0,
                )
            ),
        )

        return ExecutivePredictiveRiskClass(
            highest.risk_class
        )

    @staticmethod
    def _expected_outlook(
        risk_class: (
            ExecutivePredictiveRiskClass
        ),
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> ExecutivePredictiveOutlook:
        if not records:
            return (
                ExecutivePredictiveOutlook.STABLE
            )

        if (
            risk_class
            is ExecutivePredictiveRiskClass.CRITICAL
        ):
            return (
                ExecutivePredictiveOutlook.CRITICAL
            )

        if (
            risk_class
            is ExecutivePredictiveRiskClass.HIGH
        ):
            return (
                ExecutivePredictiveOutlook.DEGRADING
            )

        if (
            risk_class
            is ExecutivePredictiveRiskClass.MEDIUM
        ):
            return (
                ExecutivePredictiveOutlook.WATCH
            )

        return ExecutivePredictiveOutlook.STABLE

    @staticmethod
    def _expected_health_score(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> float:
        from app.services.executive_predictive_report_builder import (
            RISK_WEIGHT,
        )

        if not records:
            return 100.0

        penalty = sum(
            RISK_WEIGHT.get(
                record.risk_class,
                0.0,
            )
            * (
                record.probability_percent
                / 100
            )
            for record in records
        )

        return round(
            max(
                0.0,
                100.0 - penalty,
            ),
            2,
        )

    def validate(
        self,
        *,
        report: ExecutivePredictiveReport,
        store: PredictiveIntelligenceStore,
        source_audit: (
            PredictiveIntelligenceStoreAuditReport
        ),
        validated_at: datetime | None = None,
    ) -> ExecutivePredictiveReportValidationResult:
        if not isinstance(
            report,
            ExecutivePredictiveReport,
        ):
            raise TypeError(
                "report must be an "
                "ExecutivePredictiveReport"
            )

        if not isinstance(
            store,
            PredictiveIntelligenceStore,
        ):
            raise TypeError(
                "store must be a "
                "PredictiveIntelligenceStore"
            )

        if not isinstance(
            source_audit,
            PredictiveIntelligenceStoreAuditReport,
        ):
            raise TypeError(
                "source_audit must be a "
                "PredictiveIntelligenceStoreAuditReport"
            )

        resolved_validated_at = (
            self._normalize_validated_at(
                validated_at
            )
        )

        records = store.list_records(
            limit=1_000_000
        )

        checks: dict[str, bool] = {}
        errors: list[str] = []

        checks["fingerprint_valid"] = (
            report.report_fingerprint
            == report.calculate_fingerprint()
        )

        checks["source_audit_valid"] = (
            source_audit.audit_valid
            and report.source_audit_valid
            and report.source_audit_id
            == source_audit.audit_id
        )

        checks["source_record_count_valid"] = (
            source_audit.record_count
            == len(
                records
            )
            == report.prediction_count
        )

        expected_prediction_ids = tuple(
            record.prediction_id
            for record in records
        )

        expected_record_hashes = tuple(
            record.record_hash
            for record in records
        )

        checks[
            "source_prediction_bindings_valid"
        ] = (
            report.source_prediction_ids
            == expected_prediction_ids
        )

        checks[
            "source_record_hashes_valid"
        ] = (
            report.source_record_hashes
            == expected_record_hashes
        )

        if records:
            try:
                expected_period_start = min(
                    self._record_datetime(
                        record,
                        "observed_at",
                    )
                    for record in records
                )

                expected_period_end = max(
                    self._record_datetime(
                        record,
                        "prediction_window_end",
                    )
                    for record in records
                )

                checks["report_period_valid"] = (
                    report.report_period_start
                    == expected_period_start
                    and report.report_period_end
                    == expected_period_end
                    and report.report_period_end
                    > report.report_period_start
                )

            except ValueError:
                checks["report_period_valid"] = False

        else:
            checks["report_period_valid"] = (
                report.report_period_end
                > report.report_period_start
                and (
                    report.report_period_end
                    - report.report_period_start
                ).total_seconds()
                == 1
            )

        checks["generated_at_valid"] = (
            report.generated_at
            >= report.report_period_end
            and resolved_validated_at
            >= report.generated_at
        )

        critical_count = sum(
            1
            for record in records
            if record.risk_class == "critical"
        )

        high_count = sum(
            1
            for record in records
            if record.risk_class == "high"
        )

        checks["prediction_counts_valid"] = (
            report.prediction_count
            == len(
                records
            )
            and report.critical_prediction_count
            == critical_count
            and report.high_risk_prediction_count
            == high_count
        )

        expected_risk = self._expected_risk(
            records
        )

        checks["risk_class_valid"] = (
            report.overall_risk_class
            is expected_risk
        )

        checks["service_outlook_valid"] = (
            report.service_outlook
            is self._expected_outlook(
                expected_risk,
                records,
            )
        )

        checks["health_score_valid"] = (
            report.overall_health_score
            == self._expected_health_score(
                records
            )
        )

        checks["required_content_valid"] = (
            bool(
                report.executive_summary.strip()
            )
            and (
                not records
                or bool(
                    report.key_findings
                )
            )
            and (
                expected_risk
                not in {
                    ExecutivePredictiveRiskClass.HIGH,
                    ExecutivePredictiveRiskClass.CRITICAL,
                }
                or bool(
                    report.risk_highlights
                )
            )
        )

        checks["builder_identity_valid"] = (
            report.generated_by
            == SERVICE_NAME
            and report.metadata.get(
                "builder_service"
            )
            == SERVICE_NAME
            and bool(
                str(
                    report.metadata.get(
                        "builder_version",
                        "",
                    )
                ).strip()
            )
        )

        checks["schema_version_valid"] = (
            report.schema_version == "1.0"
        )

        payload = report.to_dict()

        checks["safety_claims_valid"] = all(
            (
                payload.get(
                    "report_created"
                )
                is True,
                payload.get(
                    "pdf_rendered"
                )
                is False,
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
                report.pdf_rendered is False,
                report.incident_created is False,
                report.recommendation_executed is False,
                report.decision_created is False,
                report.authorization_created is False,
                report.execution_allowed is False,
                report.can_execute is False,
            )
        )

        for check_name in self.REQUIRED_CHECKS:
            if not checks.get(
                check_name,
                False,
            ):
                errors.append(
                    f"{check_name} failed"
                )

        validation_valid = (
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

        return (
            ExecutivePredictiveReportValidationResult(
                report_id=(
                    report.report_id
                ),
                report_fingerprint=(
                    report.report_fingerprint
                ),
                validation_valid=(
                    validation_valid
                ),
                report_accepted=(
                    validation_valid
                ),
                validation_errors=tuple(
                    errors
                ),
                checks=checks,
                validated_at=(
                    resolved_validated_at
                ),
                validator_name=(
                    VALIDATION_SERVICE_NAME
                ),
                validator_version=(
                    VALIDATION_SERVICE_VERSION
                ),
            )
        )


def validate_executive_predictive_report(
    *,
    report: ExecutivePredictiveReport,
    store: PredictiveIntelligenceStore,
    source_audit: (
        PredictiveIntelligenceStoreAuditReport
    ),
    validated_at: datetime | None = None,
) -> ExecutivePredictiveReportValidationResult:
    return (
        ExecutivePredictiveReportValidator()
        .validate(
            report=report,
            store=store,
            source_audit=source_audit,
            validated_at=validated_at,
        )
    )
