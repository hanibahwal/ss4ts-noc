from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.executive_predictive_report import (
    ExecutivePredictiveOutlook,
    ExecutivePredictiveReport,
    ExecutivePredictiveReportType,
    ExecutivePredictiveRiskClass,
)
from app.services.predictive_intelligence_store import (
    PredictiveIntelligenceRecord,
    PredictiveIntelligenceStore,
)
from app.services.predictive_intelligence_store_audit import (
    PredictiveIntelligenceStoreAuditReport,
)


SERVICE_NAME = (
    "SS4TS Executive Predictive Report Builder"
)

SERVICE_VERSION = "1.0.0"


RISK_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


RISK_WEIGHT = {
    "low": 2.0,
    "medium": 7.0,
    "high": 15.0,
    "critical": 25.0,
}


CAPACITY_PREDICTION_TYPES = {
    "capacity_exhaustion",
    "traffic_spike",
    "throughput_decrease",
}


def _unique_texts(
    values: list[str],
) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        text = str(
            value
        ).strip()

        if (
            not text
            or text in seen
        ):
            continue

        normalized.append(
            text
        )
        seen.add(
            text
        )

    return tuple(
        normalized
    )


def _parse_datetime(
    value: Any,
    *,
    field_name: str,
) -> datetime:
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


def _normalize_generated_at(
    generated_at: datetime | None,
) -> datetime:
    value = (
        generated_at
        or datetime.now(
            timezone.utc
        )
    )

    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "generated_at must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "generated_at must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


class ExecutivePredictiveReportBuilder:
    @staticmethod
    def _overall_risk(
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
    def _health_score(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> float:
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

    @staticmethod
    def _service_outlook(
        overall_risk: (
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
            overall_risk
            is ExecutivePredictiveRiskClass.CRITICAL
        ):
            return (
                ExecutivePredictiveOutlook.CRITICAL
            )

        if (
            overall_risk
            is ExecutivePredictiveRiskClass.HIGH
        ):
            return (
                ExecutivePredictiveOutlook.DEGRADING
            )

        if (
            overall_risk
            is ExecutivePredictiveRiskClass.MEDIUM
        ):
            return (
                ExecutivePredictiveOutlook.WATCH
            )

        return ExecutivePredictiveOutlook.STABLE

    @staticmethod
    def _affected_entities(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> tuple[
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
        tuple[str, ...],
    ]:
        sites: list[str] = []
        devices: list[str] = []
        links: list[str] = []
        services: list[str] = []

        for record in records:
            site = str(
                record.metadata.get(
                    "site",
                    "",
                )
            ).strip()

            if site:
                sites.append(
                    site
                )

            if record.subject_type == "site":
                sites.append(
                    record.subject_id
                )

            elif record.subject_type == "device":
                devices.append(
                    record.subject_id
                )

            elif record.subject_type in {
                "interface",
                "link",
            }:
                links.append(
                    record.subject_id
                )

            elif record.subject_type == "service":
                services.append(
                    record.subject_id
                )

        return (
            _unique_texts(
                sites
            ),
            _unique_texts(
                devices
            ),
            _unique_texts(
                links
            ),
            _unique_texts(
                services
            ),
        )

    @staticmethod
    def _key_findings(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> tuple[str, ...]:
        findings: list[str] = []

        for record in records:
            findings.append(
                (
                    f"{record.prediction_type} predicted "
                    f"for {record.subject_id} with "
                    f"{record.probability_percent:.2f}% "
                    "probability"
                )
            )

        return _unique_texts(
            findings
        )

    @staticmethod
    def _risk_highlights(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> tuple[str, ...]:
        highlights: list[str] = []

        for record in records:
            if record.risk_class not in {
                "high",
                "critical",
            }:
                continue

            highlights.append(
                (
                    f"{record.risk_class.upper()} risk: "
                    f"{record.prediction_type} affecting "
                    f"{record.subject_id}"
                )
            )

        return _unique_texts(
            highlights
        )

    @staticmethod
    def _capacity_forecast(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> tuple[str, ...]:
        forecasts: list[str] = []

        for record in records:
            if (
                record.prediction_type
                not in CAPACITY_PREDICTION_TYPES
            ):
                continue

            if (
                record.current_value is not None
                and record.predicted_value is not None
            ):
                forecasts.append(
                    (
                        f"{record.subject_id}: "
                        f"{record.current_value:g} "
                        f"to {record.predicted_value:g} "
                        f"{record.unit or ''}"
                    ).strip()
                )
            else:
                forecasts.append(
                    (
                        f"Capacity risk predicted for "
                        f"{record.subject_id}"
                    )
                )

        return _unique_texts(
            forecasts
        )

    @staticmethod
    def _recommended_priorities(
        records: tuple[
            PredictiveIntelligenceRecord,
            ...,
        ],
    ) -> tuple[str, ...]:
        priorities: list[str] = []

        ordered_records = sorted(
            records,
            key=lambda record: (
                RISK_RANK.get(
                    record.risk_class,
                    0,
                ),
                record.probability_percent,
            ),
            reverse=True,
        )

        for record in ordered_records:
            if record.risk_class == "critical":
                priorities.append(
                    (
                        "Immediately review predicted "
                        f"{record.prediction_type} for "
                        f"{record.subject_id}"
                    )
                )

            elif record.risk_class == "high":
                priorities.append(
                    (
                        "Prioritize investigation of "
                        f"{record.subject_id}"
                    )
                )

            elif (
                record.prediction_type
                in CAPACITY_PREDICTION_TYPES
            ):
                priorities.append(
                    (
                        "Review capacity planning for "
                        f"{record.subject_id}"
                    )
                )

        if (
            records
            and not priorities
        ):
            priorities.append(
                "Continue monitoring predictive indicators"
            )

        return _unique_texts(
            priorities
        )

    @staticmethod
    def _executive_summary(
        *,
        prediction_count: int,
        critical_count: int,
        high_count: int,
        health_score: float,
        overall_risk: (
            ExecutivePredictiveRiskClass
        ),
    ) -> str:
        if prediction_count == 0:
            return (
                "No predictive risks were recorded "
                "for the reporting period."
            )

        return (
            f"{prediction_count} predictive risk records "
            f"were reviewed. {critical_count} critical and "
            f"{high_count} high-risk predictions were "
            f"identified. Overall risk is "
            f"{overall_risk.value} and the calculated "
            f"network health score is {health_score:.2f}%."
        )

    def build(
        self,
        *,
        store: PredictiveIntelligenceStore,
        source_audit: (
            PredictiveIntelligenceStoreAuditReport
        ),
        report_type: (
            ExecutivePredictiveReportType
            | str
        ),
        report_title: str,
        generated_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutivePredictiveReport:
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

        if not source_audit.audit_valid:
            raise ValueError(
                "source_audit must be valid"
            )

        records = store.list_records(
            limit=1_000_000
        )

        if (
            len(records)
            != source_audit.record_count
        ):
            raise ValueError(
                "source_audit record count does not "
                "match the predictive store"
            )

        resolved_generated_at = (
            _normalize_generated_at(
                generated_at
            )
        )

        if records:
            report_period_start = min(
                _parse_datetime(
                    record.observed_at,
                    field_name="observed_at",
                )
                for record in records
            )

            report_period_end = max(
                _parse_datetime(
                    record.prediction_window_end,
                    field_name=(
                        "prediction_window_end"
                    ),
                )
                for record in records
            )

        else:
            report_period_end = (
                resolved_generated_at
            )

            report_period_start = (
                resolved_generated_at
            )

            report_period_start = (
                report_period_start.replace(
                    microsecond=0
                )
            )

            report_period_end = (
                report_period_start
            )

            report_period_start = (
                report_period_start.replace(
                    second=max(
                        0,
                        report_period_start.second - 1,
                    )
                )
            )

            if (
                report_period_start
                >= report_period_end
            ):
                from datetime import timedelta

                report_period_start = (
                    report_period_end
                    - timedelta(
                        seconds=1
                    )
                )

        if (
            resolved_generated_at
            < report_period_end
        ):
            raise ValueError(
                "generated_at must not be earlier "
                "than the report period end"
            )

        overall_risk = self._overall_risk(
            records
        )

        health_score = self._health_score(
            records
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

        (
            affected_sites,
            affected_devices,
            affected_links,
            affected_services,
        ) = self._affected_entities(
            records
        )

        return ExecutivePredictiveReport(
            report_type=report_type,
            report_title=report_title,
            report_period_start=(
                report_period_start
            ),
            report_period_end=(
                report_period_end
            ),
            generated_at=(
                resolved_generated_at
            ),
            executive_summary=(
                self._executive_summary(
                    prediction_count=len(
                        records
                    ),
                    critical_count=(
                        critical_count
                    ),
                    high_count=(
                        high_count
                    ),
                    health_score=(
                        health_score
                    ),
                    overall_risk=(
                        overall_risk
                    ),
                )
            ),
            overall_risk_class=(
                overall_risk
            ),
            overall_health_score=(
                health_score
            ),
            service_outlook=(
                self._service_outlook(
                    overall_risk,
                    records,
                )
            ),
            prediction_count=len(
                records
            ),
            critical_prediction_count=(
                critical_count
            ),
            high_risk_prediction_count=(
                high_count
            ),
            affected_sites=(
                affected_sites
            ),
            affected_devices=(
                affected_devices
            ),
            affected_links=(
                affected_links
            ),
            affected_services=(
                affected_services
            ),
            key_findings=(
                self._key_findings(
                    records
                )
            ),
            risk_highlights=(
                self._risk_highlights(
                    records
                )
            ),
            capacity_forecast=(
                self._capacity_forecast(
                    records
                )
            ),
            recommended_priorities=(
                self._recommended_priorities(
                    records
                )
            ),
            source_prediction_ids=tuple(
                record.prediction_id
                for record in records
            ),
            source_record_hashes=tuple(
                record.record_hash
                for record in records
            ),
            source_audit_id=(
                source_audit.audit_id
            ),
            source_audit_valid=(
                source_audit.audit_valid
            ),
            generated_by=SERVICE_NAME,
            schema_version="1.0",
            metadata={
                **(
                    metadata
                    or {}
                ),
                "builder_service": (
                    SERVICE_NAME
                ),
                "builder_version": (
                    SERVICE_VERSION
                ),
            },
        )


def build_executive_predictive_report(
    *,
    store: PredictiveIntelligenceStore,
    source_audit: (
        PredictiveIntelligenceStoreAuditReport
    ),
    report_type: (
        ExecutivePredictiveReportType
        | str
    ),
    report_title: str,
    generated_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> ExecutivePredictiveReport:
    return (
        ExecutivePredictiveReportBuilder()
        .build(
            store=store,
            source_audit=source_audit,
            report_type=report_type,
            report_title=report_title,
            generated_at=generated_at,
            metadata=metadata,
        )
    )
