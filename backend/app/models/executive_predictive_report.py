from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from math import isfinite
from typing import Any
from uuid import uuid4


EXECUTIVE_PREDICTIVE_REPORT_VERSION = "1.0"


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


def _required_text(
    value: Any,
    *,
    field_name: str,
) -> str:
    normalized = str(
        value
        if value is not None
        else ""
    ).strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _aware_utc_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            f"{field_name} must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


def _percentage(
    value: Any,
    *,
    field_name: str,
) -> float:
    try:
        normalized = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be numeric"
        ) from exc

    if (
        not isfinite(normalized)
        or not 0 <= normalized <= 100
    ):
        raise ValueError(
            f"{field_name} must be between 0 and 100"
        )

    return round(
        normalized,
        2,
    )


def _non_negative_integer(
    value: Any,
    *,
    field_name: str,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{field_name} must be a non-negative integer"
        )

    try:
        normalized = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field_name} must be a non-negative integer"
        ) from exc

    if normalized < 0:
        raise ValueError(
            f"{field_name} must be a non-negative integer"
        )

    return normalized


def _unique_texts(
    values: Any,
) -> tuple[str, ...]:
    if values is None:
        return ()

    if isinstance(
        values,
        str,
    ):
        values = (
            values,
        )

    normalized: list[str] = []
    seen: set[str] = set()

    for item in values:
        text = str(
            item
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


def _normalized_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if value is None:
        return {}

    if not isinstance(
        value,
        dict,
    ):
        raise TypeError(
            f"{field_name} must be a dictionary"
        )

    return {
        str(key).strip(): item
        for key, item in value.items()
        if str(key).strip()
    }


class ExecutivePredictiveReportType(
    StrEnum
):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INCIDENT_FOCUSED = "incident_focused"
    SITE_FOCUSED = "site_focused"
    CAPACITY_FORECAST = "capacity_forecast"
    RISK_OVERVIEW = "risk_overview"


class ExecutivePredictiveRiskClass(
    StrEnum
):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExecutivePredictiveOutlook(
    StrEnum
):
    IMPROVING = "improving"
    STABLE = "stable"
    WATCH = "watch"
    DEGRADING = "degrading"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(
    frozen=True,
    slots=True,
)
class ExecutivePredictiveReport:
    report_type: ExecutivePredictiveReportType
    report_title: str

    report_period_start: datetime
    report_period_end: datetime
    generated_at: datetime

    executive_summary: str
    overall_risk_class: ExecutivePredictiveRiskClass
    overall_health_score: float
    service_outlook: ExecutivePredictiveOutlook

    prediction_count: int
    critical_prediction_count: int
    high_risk_prediction_count: int

    report_id: str = field(
        default_factory=lambda: (
            f"executive-predictive-report:{uuid4()}"
        )
    )

    affected_sites: tuple[str, ...] = ()
    affected_devices: tuple[str, ...] = ()
    affected_links: tuple[str, ...] = ()
    affected_services: tuple[str, ...] = ()

    key_findings: tuple[str, ...] = ()
    risk_highlights: tuple[str, ...] = ()
    capacity_forecast: tuple[str, ...] = ()
    recommended_priorities: tuple[str, ...] = ()

    source_prediction_ids: tuple[str, ...] = ()
    source_record_hashes: tuple[str, ...] = ()

    source_audit_id: str = ""
    source_audit_valid: bool = False

    generated_by: str = (
        "ss4ts-executive-predictive-report"
    )

    schema_version: str = (
        EXECUTIVE_PREDICTIVE_REPORT_VERSION
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    report_fingerprint: str = ""

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "report_id",
            "report_title",
            "executive_summary",
            "source_audit_id",
            "generated_by",
            "schema_version",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        for field_name, enum_type in (
            (
                "report_type",
                ExecutivePredictiveReportType,
            ),
            (
                "overall_risk_class",
                ExecutivePredictiveRiskClass,
            ),
            (
                "service_outlook",
                ExecutivePredictiveOutlook,
            ),
        ):
            value = getattr(
                self,
                field_name,
            )

            if not isinstance(
                value,
                enum_type,
            ):
                try:
                    value = enum_type(
                        str(value).strip().lower()
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"{field_name} is unsupported"
                    ) from exc

                object.__setattr__(
                    self,
                    field_name,
                    value,
                )

        for field_name in (
            "report_period_start",
            "report_period_end",
            "generated_at",
        ):
            object.__setattr__(
                self,
                field_name,
                _aware_utc_datetime(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        if (
            self.report_period_end
            <= self.report_period_start
        ):
            raise ValueError(
                "report_period_end must be later "
                "than report_period_start"
            )

        if (
            self.generated_at
            < self.report_period_end
        ):
            raise ValueError(
                "generated_at must not be earlier "
                "than report_period_end"
            )

        object.__setattr__(
            self,
            "overall_health_score",
            _percentage(
                self.overall_health_score,
                field_name="overall_health_score",
            ),
        )

        for field_name in (
            "prediction_count",
            "critical_prediction_count",
            "high_risk_prediction_count",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_integer(
                    getattr(
                        self,
                        field_name,
                    ),
                    field_name=field_name,
                ),
            )

        if (
            self.critical_prediction_count
            > self.prediction_count
        ):
            raise ValueError(
                "critical_prediction_count must not "
                "exceed prediction_count"
            )

        if (
            self.high_risk_prediction_count
            > self.prediction_count
        ):
            raise ValueError(
                "high_risk_prediction_count must not "
                "exceed prediction_count"
            )

        if (
            self.critical_prediction_count
            + self.high_risk_prediction_count
            > self.prediction_count
        ):
            raise ValueError(
                "critical and high-risk counts must not "
                "exceed prediction_count"
            )

        for field_name in (
            "affected_sites",
            "affected_devices",
            "affected_links",
            "affected_services",
            "key_findings",
            "risk_highlights",
            "capacity_forecast",
            "recommended_priorities",
            "source_prediction_ids",
            "source_record_hashes",
        ):
            object.__setattr__(
                self,
                field_name,
                _unique_texts(
                    getattr(
                        self,
                        field_name,
                    )
                ),
            )

        if (
            self.prediction_count
            != len(
                self.source_prediction_ids
            )
        ):
            raise ValueError(
                "prediction_count must match the number "
                "of source_prediction_ids"
            )

        if (
            len(self.source_record_hashes)
            != len(self.source_prediction_ids)
        ):
            raise ValueError(
                "source_record_hashes count must match "
                "source_prediction_ids count"
            )

        if not self.source_audit_valid:
            raise ValueError(
                "source_audit_valid must be true"
            )

        if (
            self.prediction_count > 0
            and not self.key_findings
        ):
            raise ValueError(
                "key_findings are required when the "
                "report contains predictions"
            )

        if (
            self.overall_risk_class
            in {
                ExecutivePredictiveRiskClass.HIGH,
                ExecutivePredictiveRiskClass.CRITICAL,
            }
            and not self.risk_highlights
        ):
            raise ValueError(
                "risk_highlights are required for "
                "high-risk or critical reports"
            )

        object.__setattr__(
            self,
            "metadata",
            _normalized_mapping(
                self.metadata,
                field_name="metadata",
            ),
        )

        expected_fingerprint = (
            self.calculate_fingerprint()
        )

        if not self.report_fingerprint:
            object.__setattr__(
                self,
                "report_fingerprint",
                expected_fingerprint,
            )
        else:
            normalized_fingerprint = (
                _required_text(
                    self.report_fingerprint,
                    field_name=(
                        "report_fingerprint"
                    ),
                ).lower()
            )

            if (
                len(normalized_fingerprint) != 64
                or any(
                    character
                    not in "0123456789abcdef"
                    for character
                    in normalized_fingerprint
                )
            ):
                raise ValueError(
                    "report_fingerprint must be "
                    "a SHA-256 hash"
                )

            if (
                normalized_fingerprint
                != expected_fingerprint
            ):
                raise ValueError(
                    "report_fingerprint mismatch"
                )

            object.__setattr__(
                self,
                "report_fingerprint",
                normalized_fingerprint,
            )

    @property
    def report_created(
        self,
    ) -> bool:
        return True

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

    def fingerprint_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "report_id":
                self.report_id,
            "report_type":
                self.report_type.value,
            "report_title":
                self.report_title,
            "report_period_start":
                self.report_period_start.isoformat(),
            "report_period_end":
                self.report_period_end.isoformat(),
            "generated_at":
                self.generated_at.isoformat(),
            "executive_summary":
                self.executive_summary,
            "overall_risk_class":
                self.overall_risk_class.value,
            "overall_health_score":
                self.overall_health_score,
            "service_outlook":
                self.service_outlook.value,
            "prediction_count":
                self.prediction_count,
            "critical_prediction_count":
                self.critical_prediction_count,
            "high_risk_prediction_count":
                self.high_risk_prediction_count,
            "affected_sites":
                list(self.affected_sites),
            "affected_devices":
                list(self.affected_devices),
            "affected_links":
                list(self.affected_links),
            "affected_services":
                list(self.affected_services),
            "key_findings":
                list(self.key_findings),
            "risk_highlights":
                list(self.risk_highlights),
            "capacity_forecast":
                list(self.capacity_forecast),
            "recommended_priorities":
                list(self.recommended_priorities),
            "source_prediction_ids":
                list(self.source_prediction_ids),
            "source_record_hashes":
                list(self.source_record_hashes),
            "source_audit_id":
                self.source_audit_id,
            "source_audit_valid":
                self.source_audit_valid,
            "generated_by":
                self.generated_by,
            "schema_version":
                self.schema_version,
            "metadata":
                self.metadata,
        }

    def calculate_fingerprint(
        self,
    ) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.fingerprint_payload()
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            **self.fingerprint_payload(),
            "report_fingerprint":
                self.report_fingerprint,
            "report_created":
                True,
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
                "executive_reporting_only":
                    True,
                "read_only_contract":
                    True,
                "source_audit_required":
                    True,
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
