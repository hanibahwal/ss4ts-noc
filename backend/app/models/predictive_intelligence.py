from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from math import isfinite
from typing import Any
from uuid import uuid4


PREDICTIVE_INTELLIGENCE_VERSION = "1.0"


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


def _optional_text(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    return normalized or None


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
        not isfinite(
            normalized
        )
        or not 0 <= normalized <= 100
    ):
        raise ValueError(
            f"{field_name} must be between 0 and 100"
        )

    return round(
        normalized,
        2,
    )


def _optional_number(
    value: Any,
    *,
    field_name: str,
) -> float | None:
    if value is None:
        return None

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

    if not isfinite(
        normalized
    ):
        raise ValueError(
            f"{field_name} must be finite"
        )

    return round(
        normalized,
        6,
    )


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
        str(
            key
        ).strip(): item
        for key, item in value.items()
        if str(
            key
        ).strip()
    }


class PredictiveIntelligenceType(
    StrEnum
):
    LINK_DEGRADATION = "link_degradation"
    CAPACITY_EXHAUSTION = "capacity_exhaustion"
    DEVICE_FAILURE = "device_failure"
    INTERFACE_FAILURE = "interface_failure"

    PACKET_LOSS_INCREASE = "packet_loss_increase"
    LATENCY_INCREASE = "latency_increase"
    JITTER_INCREASE = "jitter_increase"
    THROUGHPUT_DECREASE = "throughput_decrease"

    SIGNAL_DEGRADATION = "signal_degradation"
    SERVICE_OUTAGE = "service_outage"
    TRAFFIC_SPIKE = "traffic_spike"
    AVAILABILITY_DECREASE = "availability_decrease"


class PredictiveSubjectType(
    StrEnum
):
    DEVICE = "device"
    INTERFACE = "interface"
    LINK = "link"
    SITE = "site"
    SERVICE = "service"
    NETWORK = "network"


class PredictiveRiskClass(
    StrEnum
):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PredictiveSeverity(
    StrEnum
):
    INFO = "info"
    WARNING = "warning"
    MAJOR = "major"
    CRITICAL = "critical"


class PredictiveState(
    StrEnum
):
    STABLE = "stable"
    DEGRADED = "degraded"
    AT_RISK = "at_risk"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(
    frozen=True,
    slots=True,
)
class PredictiveIntelligence:
    prediction_type: PredictiveIntelligenceType
    subject_type: PredictiveSubjectType
    subject_id: str

    observed_at: datetime
    prediction_window_start: datetime
    prediction_window_end: datetime

    current_state: PredictiveState
    predicted_state: PredictiveState

    confidence_percent: float
    probability_percent: float

    risk_class: PredictiveRiskClass
    severity: PredictiveSeverity

    prediction_id: str = field(
        default_factory=lambda: (
            f"predictive-intelligence:{uuid4()}"
        )
    )

    current_value: float | None = None
    predicted_value: float | None = None
    unit: str | None = None

    evidence: tuple[str, ...] = ()
    contributing_factors: tuple[str, ...] = ()

    model_name: str = (
        "ss4ts-predictive-intelligence"
    )
    model_version: str = (
        PREDICTIVE_INTELLIGENCE_VERSION
    )

    source_metric_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=lambda: (
            datetime.now(
                timezone.utc
            )
        )
    )

    prediction_fingerprint: str = ""

    def __post_init__(
        self,
    ) -> None:
        object.__setattr__(
            self,
            "prediction_id",
            _required_text(
                self.prediction_id,
                field_name="prediction_id",
            ),
        )

        object.__setattr__(
            self,
            "subject_id",
            _required_text(
                self.subject_id,
                field_name="subject_id",
            ),
        )

        object.__setattr__(
            self,
            "model_name",
            _required_text(
                self.model_name,
                field_name="model_name",
            ),
        )

        object.__setattr__(
            self,
            "model_version",
            _required_text(
                self.model_version,
                field_name="model_version",
            ),
        )

        for field_name, enum_type in (
            (
                "prediction_type",
                PredictiveIntelligenceType,
            ),
            (
                "subject_type",
                PredictiveSubjectType,
            ),
            (
                "current_state",
                PredictiveState,
            ),
            (
                "predicted_state",
                PredictiveState,
            ),
            (
                "risk_class",
                PredictiveRiskClass,
            ),
            (
                "severity",
                PredictiveSeverity,
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
                        str(
                            value
                        ).strip().lower()
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
            "observed_at",
            "prediction_window_start",
            "prediction_window_end",
            "created_at",
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
            self.prediction_window_start
            < self.observed_at
        ):
            raise ValueError(
                "prediction_window_start must not "
                "be earlier than observed_at"
            )

        if (
            self.prediction_window_end
            <= self.prediction_window_start
        ):
            raise ValueError(
                "prediction_window_end must be later "
                "than prediction_window_start"
            )

        if self.created_at < self.observed_at:
            raise ValueError(
                "created_at must not be earlier "
                "than observed_at"
            )

        object.__setattr__(
            self,
            "confidence_percent",
            _percentage(
                self.confidence_percent,
                field_name="confidence_percent",
            ),
        )

        object.__setattr__(
            self,
            "probability_percent",
            _percentage(
                self.probability_percent,
                field_name="probability_percent",
            ),
        )

        object.__setattr__(
            self,
            "current_value",
            _optional_number(
                self.current_value,
                field_name="current_value",
            ),
        )

        object.__setattr__(
            self,
            "predicted_value",
            _optional_number(
                self.predicted_value,
                field_name="predicted_value",
            ),
        )

        object.__setattr__(
            self,
            "unit",
            _optional_text(
                self.unit
            ),
        )

        if (
            (
                self.current_value is not None
                or self.predicted_value is not None
            )
            and self.unit is None
        ):
            raise ValueError(
                "unit is required when current_value "
                "or predicted_value is provided"
            )

        object.__setattr__(
            self,
            "evidence",
            _unique_texts(
                self.evidence
            ),
        )

        object.__setattr__(
            self,
            "contributing_factors",
            _unique_texts(
                self.contributing_factors
            ),
        )

        object.__setattr__(
            self,
            "source_metric_ids",
            _unique_texts(
                self.source_metric_ids
            ),
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

        if not self.prediction_fingerprint:
            object.__setattr__(
                self,
                "prediction_fingerprint",
                expected_fingerprint,
            )
        else:
            normalized_fingerprint = (
                _required_text(
                    self.prediction_fingerprint,
                    field_name=(
                        "prediction_fingerprint"
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
                    "prediction_fingerprint must be "
                    "a SHA-256 hash"
                )

            if (
                normalized_fingerprint
                != expected_fingerprint
            ):
                raise ValueError(
                    "prediction_fingerprint mismatch"
                )

            object.__setattr__(
                self,
                "prediction_fingerprint",
                normalized_fingerprint,
            )

    @property
    def prediction_created(
        self,
    ) -> bool:
        return True

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

    def fingerprint_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "prediction_id":
                self.prediction_id,
            "prediction_type":
                self.prediction_type.value,
            "subject_type":
                self.subject_type.value,
            "subject_id":
                self.subject_id,
            "observed_at":
                self.observed_at.isoformat(),
            "prediction_window_start":
                self.prediction_window_start.isoformat(),
            "prediction_window_end":
                self.prediction_window_end.isoformat(),
            "current_state":
                self.current_state.value,
            "predicted_state":
                self.predicted_state.value,
            "current_value":
                self.current_value,
            "predicted_value":
                self.predicted_value,
            "unit":
                self.unit,
            "confidence_percent":
                self.confidence_percent,
            "probability_percent":
                self.probability_percent,
            "risk_class":
                self.risk_class.value,
            "severity":
                self.severity.value,
            "evidence":
                list(
                    self.evidence
                ),
            "contributing_factors":
                list(
                    self.contributing_factors
                ),
            "model_name":
                self.model_name,
            "model_version":
                self.model_version,
            "source_metric_ids":
                list(
                    self.source_metric_ids
                ),
            "metadata":
                self.metadata,
            "created_at":
                self.created_at.isoformat(),
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
            "prediction_fingerprint":
                self.prediction_fingerprint,
            "prediction_created":
                True,
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
                "predictive_analysis_only":
                    True,
                "read_only_contract":
                    True,
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
