from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import StrEnum
from math import isfinite
from typing import Any

from app.models.decision import (
    Evidence,
    RiskLevel,
)


class PredictionType(StrEnum):
    CAPACITY = "capacity"
    SATURATION = "saturation"
    FAILURE = "failure"
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    TEMPERATURE = "temperature"
    TRAFFIC = "traffic"
    UTILIZATION = "utilization"
    ERRORS = "errors"
    DROPS = "drops"
    AVAILABILITY = "availability"
    LTE_SIGNAL = "lte_signal"
    LATENCY = "latency"
    PACKET_LOSS = "packet_loss"
    UNKNOWN = "unknown"


class PredictionDirection(StrEnum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class PredictionStatus(StrEnum):
    ACTIVE = "active"
    REACHED = "reached"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class ForecastQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT_DATA = "insufficient_data"
    UNKNOWN = "unknown"


class ForecastUnit(StrEnum):
    BPS = "bps"
    PERCENT = "percent"
    CELSIUS = "celsius"
    MILLISECONDS = "milliseconds"
    COUNT = "count"
    DBM = "dbm"
    RATIO = "ratio"
    UNKNOWN = "unknown"


class HorizonUnit(StrEnum):
    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(numeric_value):
        return default

    return numeric_value


def _optional_number(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if not isfinite(numeric_value):
        return None

    return numeric_value


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _optional_text(
    value: Any,
) -> str | None:
    text = _text(value)

    return text or None


def _clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            _number(value),
            maximum,
        ),
    )


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)

        if not text:
            return None

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                text
            )
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _datetime_to_iso(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.astimezone(
        timezone.utc
    ).isoformat()


def _normalize_prediction_type(
    value: Any,
) -> PredictionType:
    normalized = _text(
        value,
        PredictionType.UNKNOWN,
    ).lower()

    aliases = {
        "bandwidth": "traffic",
        "bandwidth_capacity": "capacity",
        "interface_failure": "failure",
        "link_failure": "failure",
        "congestion": "saturation",
        "cpu_usage": "cpu",
        "memory_usage": "memory",
        "disk": "storage",
        "disk_usage": "storage",
        "packet-loss": "packet_loss",
        "lte": "lte_signal",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return PredictionType(
            normalized
        )
    except ValueError:
        return PredictionType.UNKNOWN


def _normalize_direction(
    value: Any,
) -> PredictionDirection:
    normalized = _text(
        value,
        PredictionDirection.UNKNOWN,
    ).lower()

    aliases = {
        "up": "rising",
        "increase": "rising",
        "increasing": "rising",
        "down": "falling",
        "decrease": "falling",
        "decreasing": "falling",
        "flat": "stable",
        "unchanged": "stable",
        "unstable": "volatile",
        "fluctuating": "volatile",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return PredictionDirection(
            normalized
        )
    except ValueError:
        return PredictionDirection.UNKNOWN


def _normalize_status(
    value: Any,
) -> PredictionStatus:
    normalized = _text(
        value,
        PredictionStatus.ACTIVE,
    ).lower()

    aliases = {
        "pending": "active",
        "triggered": "reached",
        "completed": "reached",
        "cancelled": "invalidated",
        "canceled": "invalidated",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return PredictionStatus(
            normalized
        )
    except ValueError:
        return PredictionStatus.UNKNOWN


def _normalize_quality(
    value: Any,
) -> ForecastQuality:
    normalized = _text(
        value,
        ForecastQuality.UNKNOWN,
    ).lower()

    aliases = {
        "high": "excellent",
        "medium": "moderate",
        "poor": "low",
        "insufficient": "insufficient_data",
        "empty": "insufficient_data",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return ForecastQuality(
            normalized
        )
    except ValueError:
        return ForecastQuality.UNKNOWN


def _normalize_unit(
    value: Any,
) -> ForecastUnit:
    normalized = _text(
        value,
        ForecastUnit.UNKNOWN,
    ).lower()

    aliases = {
        "%": "percent",
        "percentage": "percent",
        "mbps": "bps",
        "gbps": "bps",
        "c": "celsius",
        "°c": "celsius",
        "ms": "milliseconds",
        "db": "dbm",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return ForecastUnit(
            normalized
        )
    except ValueError:
        return ForecastUnit.UNKNOWN


def _normalize_horizon_unit(
    value: Any,
) -> HorizonUnit:
    normalized = _text(
        value,
        HorizonUnit.MINUTES,
    ).lower()

    aliases = {
        "second": "seconds",
        "minute": "minutes",
        "hour": "hours",
        "day": "days",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return HorizonUnit(
            normalized
        )
    except ValueError:
        return HorizonUnit.MINUTES


def _normalize_risk(
    value: Any,
) -> RiskLevel:
    if isinstance(
        value,
        dict,
    ):
        value = value.get("level")

    normalized = _text(
        value,
        RiskLevel.UNKNOWN,
    ).lower()

    aliases = {
        "warning": "medium",
        "moderate": "medium",
        "normal": "healthy",
        "stable": "healthy",
        "excellent": "healthy",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return RiskLevel(
            normalized
        )
    except ValueError:
        return RiskLevel.UNKNOWN


def _quality_from_confidence(
    confidence_percent: float,
    sample_count: int,
) -> ForecastQuality:
    if sample_count < 3:
        return (
            ForecastQuality.INSUFFICIENT_DATA
        )

    if (
        confidence_percent >= 90
        and sample_count >= 20
    ):
        return ForecastQuality.EXCELLENT

    if confidence_percent >= 75:
        return ForecastQuality.GOOD

    if confidence_percent >= 55:
        return ForecastQuality.MODERATE

    return ForecastQuality.LOW


@dataclass(slots=True)
class ForecastHorizon:
    """
    Time horizon used by one prediction.
    """

    value: float
    unit: HorizonUnit = (
        HorizonUnit.MINUTES
    )

    @property
    def total_seconds(self) -> float:
        multiplier = {
            HorizonUnit.SECONDS: 1.0,
            HorizonUnit.MINUTES: 60.0,
            HorizonUnit.HOURS: 3600.0,
            HorizonUnit.DAYS: 86400.0,
        }.get(
            self.unit,
            60.0,
        )

        return max(
            0.0,
            self.value,
        ) * multiplier

    @property
    def total_minutes(self) -> float:
        return round(
            self.total_seconds / 60.0,
            2,
        )

    @property
    def total_hours(self) -> float:
        return round(
            self.total_seconds / 3600.0,
            2,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ForecastHorizon:
        return cls(
            value=max(
                0.0,
                _number(
                    data.get("value")
                    or data.get(
                        "horizon"
                    )
                    or data.get(
                        "minutes"
                    )
                ),
            ),

            unit=_normalize_horizon_unit(
                data.get("unit")
                or (
                    "minutes"
                    if data.get(
                        "minutes"
                    )
                    is not None
                    else None
                )
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "value": round(
                self.value,
                2,
            ),
            "unit": self.unit.value,
            "total_seconds": round(
                self.total_seconds,
                2,
            ),
            "total_minutes":
                self.total_minutes,
            "total_hours":
                self.total_hours,
        }


@dataclass(slots=True)
class ForecastRange:
    """
    Expected forecast value with lower and upper confidence bounds.
    """

    expected: float
    lower: float | None = None
    upper: float | None = None

    unit: ForecastUnit = (
        ForecastUnit.UNKNOWN
    )

    @property
    def spread(self) -> float | None:
        if (
            self.lower is None
            or self.upper is None
        ):
            return None

        return round(
            max(
                0.0,
                self.upper - self.lower,
            ),
            2,
        )

    @property
    def uncertainty_percent(
        self,
    ) -> float | None:
        spread = self.spread

        if (
            spread is None
            or self.expected == 0
        ):
            return None

        return round(
            abs(
                spread
                / self.expected
                * 100.0
            ),
            2,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ForecastRange:
        expected = _number(
            data.get("expected")
            if data.get("expected")
            is not None
            else data.get(
                "predicted_value"
            )
            if data.get(
                "predicted_value"
            )
            is not None
            else data.get("value")
        )

        lower = _optional_number(
            data.get("lower")
            if data.get("lower")
            is not None
            else data.get(
                "lower_bound"
            )
        )

        upper = _optional_number(
            data.get("upper")
            if data.get("upper")
            is not None
            else data.get(
                "upper_bound"
            )
        )

        if (
            lower is not None
            and upper is not None
            and lower > upper
        ):
            lower, upper = upper, lower

        return cls(
            expected=expected,
            lower=lower,
            upper=upper,
            unit=_normalize_unit(
                data.get("unit")
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "expected": round(
                self.expected,
                2,
            ),
            "lower": (
                round(self.lower, 2)
                if self.lower is not None
                else None
            ),
            "upper": (
                round(self.upper, 2)
                if self.upper is not None
                else None
            ),
            "unit": self.unit.value,
            "spread": self.spread,
            "uncertainty_percent":
                self.uncertainty_percent,
        }


@dataclass(slots=True)
class PredictionFactor:
    """
    One factor that positively or negatively influences a prediction.
    """

    factor_id: str
    title: str
    description: str = ""

    contribution_percent: float = 0.0
    direction: PredictionDirection = (
        PredictionDirection.UNKNOWN
    )

    evidence: list[
        Evidence
    ] = field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @property
    def absolute_contribution(
        self,
    ) -> float:
        return round(
            abs(
                self.contribution_percent
            ),
            2,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> PredictionFactor:
        raw_evidence = data.get(
            "evidence",
            [],
        )

        if isinstance(
            raw_evidence,
            dict,
        ):
            evidence = [
                Evidence(
                    key=str(key),
                    value=value,
                )
                for key, value
                in raw_evidence.items()
            ]
        else:
            evidence = [
                Evidence.from_dict(
                    item
                )
                for item in (
                    raw_evidence
                    if isinstance(
                        raw_evidence,
                        list,
                    )
                    else []
                )
                if isinstance(
                    item,
                    dict,
                )
            ]

        contribution = _number(
            data.get(
                "contribution_percent",
                data.get(
                    "contribution",
                    0,
                ),
            )
        )

        contribution = max(
            -100.0,
            min(
                contribution,
                100.0,
            ),
        )

        return cls(
            factor_id=_text(
                data.get("factor_id")
                or data.get("id")
                or "unknown-factor"
            ),

            title=_text(
                data.get("title")
                or data.get("name")
                or "Prediction factor"
            ),

            description=_text(
                data.get("description")
            ),

            contribution_percent=
                round(
                    contribution,
                    2,
                ),

            direction=_normalize_direction(
                data.get("direction")
            ),

            evidence=evidence,

            metadata=(
                dict(
                    data.get(
                        "metadata",
                        {},
                    )
                )
                if isinstance(
                    data.get(
                        "metadata",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        result = asdict(self)

        result["direction"] = (
            self.direction.value
        )

        result["evidence"] = [
            item.to_dict()
            for item in self.evidence
        ]

        result[
            "absolute_contribution"
        ] = self.absolute_contribution

        result["id"] = (
            self.factor_id
        )

        return result


@dataclass(slots=True)
class ThresholdPrediction:
    """
    Prediction describing when a metric is expected to reach a threshold.
    """

    threshold_value: float
    current_value: float

    unit: ForecastUnit = (
        ForecastUnit.UNKNOWN
    )

    estimated_time: datetime | None = None

    minutes_to_threshold: float | None = None

    already_reached: bool = False

    @property
    def remaining_value(self) -> float:
        return round(
            max(
                0.0,
                self.threshold_value
                - self.current_value,
            ),
            2,
        )

    @property
    def current_progress_percent(
        self,
    ) -> float | None:
        if self.threshold_value <= 0:
            return None

        return round(
            _clamp(
                self.current_value
                / self.threshold_value
                * 100.0
            ),
            2,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        generated_at:
            datetime | None = None,
    ) -> ThresholdPrediction:
        threshold = _number(
            data.get(
                "threshold_value",
                data.get(
                    "threshold",
                    0,
                ),
            )
        )

        current = _number(
            data.get(
                "current_value",
                data.get(
                    "current",
                    0,
                ),
            )
        )

        minutes = _optional_number(
            data.get(
                "minutes_to_threshold"
            )
        )

        estimated_time = (
            _parse_datetime(
                data.get(
                    "estimated_time"
                )
                or data.get(
                    "predicted_at"
                )
            )
        )

        base_time = (
            generated_at
            or datetime.now(
                timezone.utc
            )
        )

        if (
            estimated_time is None
            and minutes is not None
        ):
            estimated_time = (
                base_time
                + timedelta(
                    minutes=max(
                        0.0,
                        minutes,
                    )
                )
            )

        reached = bool(
            data.get(
                "already_reached",
                current >= threshold
                if threshold > 0
                else False,
            )
        )

        if reached:
            minutes = 0.0

        return cls(
            threshold_value=threshold,
            current_value=current,
            unit=_normalize_unit(
                data.get("unit")
            ),
            estimated_time=
                estimated_time,
            minutes_to_threshold=(
                max(0.0, minutes)
                if minutes is not None
                else None
            ),
            already_reached=reached,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "threshold_value": round(
                self.threshold_value,
                2,
            ),
            "current_value": round(
                self.current_value,
                2,
            ),
            "unit": self.unit.value,
            "estimated_time":
                _datetime_to_iso(
                    self.estimated_time
                ),
            "minutes_to_threshold": (
                round(
                    self.minutes_to_threshold,
                    2,
                )
                if self.minutes_to_threshold
                is not None
                else None
            ),
            "already_reached":
                self.already_reached,
            "remaining_value":
                self.remaining_value,
            "current_progress_percent":
                self.current_progress_percent,
        }


@dataclass(slots=True)
class FailurePrediction:
    """
    Failure probability and expected failure window for an entity.
    """

    probability_percent: float

    likely_cause: str | None = None

    earliest_time: datetime | None = None

    expected_time: datetime | None = None

    latest_time: datetime | None = None

    mean_time_to_failure_minutes: float | None = None

    affected_entity: str | None = None

    @property
    def risk_level(self) -> RiskLevel:
        probability = (
            self.probability_percent
        )

        if probability >= 85:
            return RiskLevel.CRITICAL

        if probability >= 65:
            return RiskLevel.HIGH

        if probability >= 40:
            return RiskLevel.MEDIUM

        if probability > 0:
            return RiskLevel.LOW

        return RiskLevel.HEALTHY

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> FailurePrediction:
        return cls(
            probability_percent=_clamp(
                data.get(
                    "probability_percent",
                    data.get(
                        "failure_probability",
                        data.get(
                            "probability",
                            0,
                        ),
                    ),
                )
            ),

            likely_cause=_optional_text(
                data.get(
                    "likely_cause"
                )
                or data.get("cause")
            ),

            earliest_time=_parse_datetime(
                data.get(
                    "earliest_time"
                )
            ),

            expected_time=_parse_datetime(
                data.get(
                    "expected_time"
                )
                or data.get(
                    "predicted_time"
                )
            ),

            latest_time=_parse_datetime(
                data.get(
                    "latest_time"
                )
            ),

            mean_time_to_failure_minutes=(
                _optional_number(
                    data.get(
                        "mean_time_to_failure_minutes"
                    )
                    or data.get(
                        "minutes_to_failure"
                    )
                )
            ),

            affected_entity=_optional_text(
                data.get(
                    "affected_entity"
                )
                or data.get(
                    "interface_name"
                )
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "probability_percent":
                round(
                    self.probability_percent,
                    2,
                ),
            "likely_cause":
                self.likely_cause,
            "earliest_time":
                _datetime_to_iso(
                    self.earliest_time
                ),
            "expected_time":
                _datetime_to_iso(
                    self.expected_time
                ),
            "latest_time":
                _datetime_to_iso(
                    self.latest_time
                ),
            "mean_time_to_failure_minutes": (
                round(
                    self.mean_time_to_failure_minutes,
                    2,
                )
                if self.mean_time_to_failure_minutes
                is not None
                else None
            ),
            "affected_entity":
                self.affected_entity,
            "risk_level":
                self.risk_level.value,
        }


@dataclass(slots=True)
class Prediction:
    """
    Canonical explainable prediction produced by SS4TS engines.
    """

    prediction_id: str
    title: str
    description: str

    prediction_type: PredictionType = (
        PredictionType.UNKNOWN
    )

    status: PredictionStatus = (
        PredictionStatus.ACTIVE
    )

    risk: RiskLevel = (
        RiskLevel.UNKNOWN
    )

    direction: PredictionDirection = (
        PredictionDirection.UNKNOWN
    )

    confidence_percent: float = 0.0
    probability_percent: float = 0.0

    quality: ForecastQuality = (
        ForecastQuality.UNKNOWN
    )

    generated_at: datetime = field(
        default_factory=lambda: (
            datetime.now(
                timezone.utc
            )
        )
    )

    valid_until: datetime | None = None

    router_ip: str | None = None
    device_name: str | None = None
    interface_name: str | None = None
    metric_name: str | None = None

    horizon: ForecastHorizon | None = None
    forecast: ForecastRange | None = None
    threshold: ThresholdPrediction | None = None
    failure: FailurePrediction | None = None

    sample_count: int = 0
    training_window_minutes: float | None = None

    factors: list[
        PredictionFactor
    ] = field(
        default_factory=list
    )

    evidence: list[
        Evidence
    ] = field(
        default_factory=list
    )

    preventive_action: str | None = None
    expected_impact: str | None = None

    model_name: str | None = None
    model_version: str | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.confidence_percent = (
            _clamp(
                self.confidence_percent
            )
        )

        self.probability_percent = (
            _clamp(
                self.probability_percent
            )
        )

        self.sample_count = max(
            0,
            _integer(
                self.sample_count
            ),
        )

        self.factors.sort(
            key=lambda item: (
                item.absolute_contribution
            ),
            reverse=True,
        )

        if (
            self.quality
            == ForecastQuality.UNKNOWN
        ):
            self.quality = (
                _quality_from_confidence(
                    self.confidence_percent,
                    self.sample_count,
                )
            )

        if (
            self.failure is not None
            and self.risk
            == RiskLevel.UNKNOWN
        ):
            self.risk = (
                self.failure.risk_level
            )

        if (
            self.threshold is not None
            and self.threshold.already_reached
        ):
            self.status = (
                PredictionStatus.REACHED
            )

    @property
    def is_actionable(self) -> bool:
        return (
            self.risk
            in {
                RiskLevel.CRITICAL,
                RiskLevel.HIGH,
                RiskLevel.MEDIUM,
            }
            or self.probability_percent
            >= 40
        )

    @property
    def is_expired(self) -> bool:
        if self.valid_until is None:
            return False

        return (
            datetime.now(
                timezone.utc
            )
            > self.valid_until
        )

    @property
    def top_factor(
        self,
    ) -> PredictionFactor | None:
        if not self.factors:
            return None

        return self.factors[0]

    @property
    def predicted_event_time(
        self,
    ) -> datetime | None:
        if (
            self.failure is not None
            and self.failure.expected_time
            is not None
        ):
            return (
                self.failure.expected_time
            )

        if (
            self.threshold is not None
            and self.threshold.estimated_time
            is not None
        ):
            return (
                self.threshold.estimated_time
            )

        if self.horizon is not None:
            return (
                self.generated_at
                + timedelta(
                    seconds=(
                        self.horizon.total_seconds
                    )
                )
            )

        return None

    @property
    def minutes_to_event(
        self,
    ) -> float | None:
        event_time = (
            self.predicted_event_time
        )

        if event_time is None:
            return None

        delta = (
            event_time
            - datetime.now(
                timezone.utc
            )
        ).total_seconds()

        return round(
            max(
                0.0,
                delta / 60.0,
            ),
            2,
        )

    @property
    def priority_score(self) -> float:
        risk_weight = {
            RiskLevel.CRITICAL: 45.0,
            RiskLevel.HIGH: 35.0,
            RiskLevel.MEDIUM: 25.0,
            RiskLevel.LOW: 12.0,
            RiskLevel.HEALTHY: 0.0,
            RiskLevel.UNKNOWN: 5.0,
        }.get(
            self.risk,
            0.0,
        )

        time_weight = 0.0

        minutes = self.minutes_to_event

        if minutes is not None:
            if minutes <= 10:
                time_weight = 20.0
            elif minutes <= 60:
                time_weight = 15.0
            elif minutes <= 1440:
                time_weight = 8.0
            else:
                time_weight = 3.0

        return round(
            min(
                100.0,
                risk_weight
                + self.confidence_percent
                * 0.2
                + self.probability_percent
                * 0.15
                + time_weight,
            ),
            2,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> Prediction:
        generated_at = (
            _parse_datetime(
                data.get(
                    "generated_at"
                )
            )
            or datetime.now(
                timezone.utc
            )
        )

        raw_horizon = data.get(
            "horizon"
        )

        horizon = None

        if isinstance(
            raw_horizon,
            dict,
        ):
            horizon = (
                ForecastHorizon.from_dict(
                    raw_horizon
                )
            )
        elif (
            data.get(
                "horizon_minutes"
            )
            is not None
        ):
            horizon = ForecastHorizon(
                value=max(
                    0.0,
                    _number(
                        data.get(
                            "horizon_minutes"
                        )
                    ),
                ),
                unit=HorizonUnit.MINUTES,
            )

        raw_forecast = data.get(
            "forecast"
        )

        forecast = (
            ForecastRange.from_dict(
                raw_forecast
            )
            if isinstance(
                raw_forecast,
                dict,
            )
            else None
        )

        raw_threshold = data.get(
            "threshold"
        )

        threshold = (
            ThresholdPrediction.from_dict(
                raw_threshold,
                generated_at=generated_at,
            )
            if isinstance(
                raw_threshold,
                dict,
            )
            else None
        )

        raw_failure = data.get(
            "failure"
        )

        failure = (
            FailurePrediction.from_dict(
                raw_failure
            )
            if isinstance(
                raw_failure,
                dict,
            )
            else None
        )

        raw_factors = data.get(
            "factors",
            [],
        )

        factors = [
            PredictionFactor.from_dict(
                item
            )
            for item in (
                raw_factors
                if isinstance(
                    raw_factors,
                    list,
                )
                else []
            )
            if isinstance(
                item,
                dict,
            )
        ]

        raw_evidence = data.get(
            "evidence",
            [],
        )

        if isinstance(
            raw_evidence,
            dict,
        ):
            evidence = [
                Evidence(
                    key=str(key),
                    value=value,
                )
                for key, value
                in raw_evidence.items()
            ]
        else:
            evidence = [
                Evidence.from_dict(
                    item
                )
                for item in (
                    raw_evidence
                    if isinstance(
                        raw_evidence,
                        list,
                    )
                    else []
                )
                if isinstance(
                    item,
                    dict,
                )
            ]

        confidence = _clamp(
            data.get(
                "confidence_percent",
                data.get(
                    "confidence",
                    0,
                ),
            )
        )

        sample_count = max(
            0,
            _integer(
                data.get(
                    "sample_count",
                    data.get(
                        "samples",
                        0,
                    ),
                )
            ),
        )

        quality_value = data.get(
            "quality"
        )

        quality = (
            _normalize_quality(
                quality_value
            )
            if quality_value
            is not None
            else _quality_from_confidence(
                confidence,
                sample_count,
            )
        )

        return cls(
            prediction_id=_text(
                data.get(
                    "prediction_id"
                )
                or data.get("id")
                or "unknown-prediction"
            ),

            title=_text(
                data.get("title")
                or "Prediction"
            ),

            description=_text(
                data.get("description")
            ),

            prediction_type=(
                _normalize_prediction_type(
                    data.get(
                        "prediction_type"
                    )
                    or data.get("type")
                    or data.get(
                        "category"
                    )
                )
            ),

            status=_normalize_status(
                data.get("status")
            ),

            risk=_normalize_risk(
                data.get("risk")
            ),

            direction=_normalize_direction(
                data.get("direction")
            ),

            confidence_percent=
                confidence,

            probability_percent=_clamp(
                data.get(
                    "probability_percent",
                    data.get(
                        "probability",
                        0,
                    ),
                )
            ),

            quality=quality,
            generated_at=generated_at,

            valid_until=_parse_datetime(
                data.get("valid_until")
                or data.get("expires_at")
            ),

            router_ip=_optional_text(
                data.get("router_ip")
                or data.get("device_ip")
            ),

            device_name=_optional_text(
                data.get("device_name")
                or data.get("identity")
            ),

            interface_name=_optional_text(
                data.get(
                    "interface_name"
                )
                or data.get(
                    "interface"
                )
            ),

            metric_name=_optional_text(
                data.get("metric_name")
                or data.get("metric")
            ),

            horizon=horizon,
            forecast=forecast,
            threshold=threshold,
            failure=failure,

            sample_count=sample_count,

            training_window_minutes=(
                _optional_number(
                    data.get(
                        "training_window_minutes"
                    )
                )
            ),

            factors=factors,
            evidence=evidence,

            preventive_action=(
                _optional_text(
                    data.get(
                        "preventive_action"
                    )
                    or data.get(
                        "recommendation"
                    )
                )
            ),

            expected_impact=(
                _optional_text(
                    data.get(
                        "expected_impact"
                    )
                )
            ),

            model_name=_optional_text(
                data.get("model_name")
            ),

            model_version=(
                _optional_text(
                    data.get(
                        "model_version"
                    )
                )
            ),

            metadata=(
                dict(
                    data.get(
                        "metadata",
                        {},
                    )
                )
                if isinstance(
                    data.get(
                        "metadata",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "prediction_id":
                self.prediction_id,

            "id":
                self.prediction_id,

            "title":
                self.title,

            "description":
                self.description,

            "prediction_type":
                self.prediction_type.value,

            "type":
                self.prediction_type.value,

            "status":
                self.status.value,

            "risk":
                self.risk.value,

            "direction":
                self.direction.value,

            "confidence_percent":
                round(
                    self.confidence_percent,
                    2,
                ),

            "confidence":
                round(
                    self.confidence_percent,
                    2,
                ),

            "probability_percent":
                round(
                    self.probability_percent,
                    2,
                ),

            "quality":
                self.quality.value,

            "generated_at":
                _datetime_to_iso(
                    self.generated_at
                ),

            "valid_until":
                _datetime_to_iso(
                    self.valid_until
                ),

            "router_ip":
                self.router_ip,

            "device_name":
                self.device_name,

            "interface_name":
                self.interface_name,

            "metric_name":
                self.metric_name,

            "horizon": (
                self.horizon.to_dict()
                if self.horizon
                else None
            ),

            "forecast": (
                self.forecast.to_dict()
                if self.forecast
                else None
            ),

            "threshold": (
                self.threshold.to_dict()
                if self.threshold
                else None
            ),

            "failure": (
                self.failure.to_dict()
                if self.failure
                else None
            ),

            "sample_count":
                self.sample_count,

            "training_window_minutes":
                self.training_window_minutes,

            "factors": [
                item.to_dict()
                for item in self.factors
            ],

            "evidence": [
                item.to_dict()
                for item in self.evidence
            ],

            "preventive_action":
                self.preventive_action,

            "expected_impact":
                self.expected_impact,

            "model_name":
                self.model_name,

            "model_version":
                self.model_version,

            "is_actionable":
                self.is_actionable,

            "is_expired":
                self.is_expired,

            "predicted_event_time":
                _datetime_to_iso(
                    self.predicted_event_time
                ),

            "minutes_to_event":
                self.minutes_to_event,

            "priority_score":
                self.priority_score,

            "top_factor": (
                self.top_factor.to_dict()
                if self.top_factor
                else None
            ),

            "metadata":
                self.metadata,
        }


@dataclass(slots=True)
class PredictionResult:
    """
    Complete normalized output of the SS4TS Prediction Engine.
    """

    router_ip: str
    device_name: str

    generated_at: datetime = field(
        default_factory=lambda: (
            datetime.now(
                timezone.utc
            )
        )
    )

    engine_name: str = (
        "SS4TS Prediction Engine"
    )

    engine_version: str = "1.6"

    predictions: list[
        Prediction
    ] = field(
        default_factory=list
    )

    summary: str = ""

    analysis_context: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    data_sources: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.predictions.sort(
            key=lambda item: (
                item.priority_score
            ),
            reverse=True,
        )

    @property
    def top_prediction(
        self,
    ) -> Prediction | None:
        if not self.predictions:
            return None

        return self.predictions[0]

    @property
    def actionable_predictions(
        self,
    ) -> list[Prediction]:
        return [
            item
            for item in self.predictions
            if item.is_actionable
        ]

    @property
    def critical_predictions(
        self,
    ) -> list[Prediction]:
        return [
            item
            for item in self.predictions
            if item.risk
            == RiskLevel.CRITICAL
        ]

    @property
    def high_predictions(
        self,
    ) -> list[Prediction]:
        return [
            item
            for item in self.predictions
            if item.risk
            == RiskLevel.HIGH
        ]

    @property
    def earliest_event_time(
        self,
    ) -> datetime | None:
        event_times = [
            item.predicted_event_time
            for item in self.predictions
            if item.predicted_event_time
            is not None
        ]

        if not event_times:
            return None

        return min(
            event_times
        )

    @property
    def overall_risk(
        self,
    ) -> RiskLevel:
        priority = {
            RiskLevel.CRITICAL: 5,
            RiskLevel.HIGH: 4,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 2,
            RiskLevel.HEALTHY: 1,
            RiskLevel.UNKNOWN: 0,
        }

        return max(
            (
                item.risk
                for item
                in self.predictions
            ),
            key=lambda risk: (
                priority.get(
                    risk,
                    0,
                )
            ),
            default=RiskLevel.HEALTHY,
        )

    @property
    def statistics(
        self,
    ) -> dict[str, Any]:
        quality_counts = {
            quality.value: sum(
                1
                for item
                in self.predictions
                if item.quality == quality
            )
            for quality
            in ForecastQuality
        }

        type_counts = {
            prediction_type.value: sum(
                1
                for item
                in self.predictions
                if (
                    item.prediction_type
                    == prediction_type
                )
            )
            for prediction_type
            in PredictionType
        }

        return {
            "prediction_count":
                len(
                    self.predictions
                ),

            "actionable_count":
                len(
                    self.actionable_predictions
                ),

            "critical_count":
                len(
                    self.critical_predictions
                ),

            "high_count":
                len(
                    self.high_predictions
                ),

            "overall_risk":
                self.overall_risk.value,

            "earliest_event_time":
                _datetime_to_iso(
                    self.earliest_event_time
                ),

            "quality_counts":
                quality_counts,

            "type_counts":
                type_counts,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> PredictionResult:
        raw_engine = data.get(
            "engine",
            {},
        )

        if not isinstance(
            raw_engine,
            dict,
        ):
            raw_engine = {}

        raw_predictions = data.get(
            "predictions",
            [],
        )

        return cls(
            router_ip=_text(
                data.get("router_ip")
                or data.get("device_ip")
            ),

            device_name=_text(
                data.get("device_name")
                or data.get("identity")
                or data.get("router_ip")
            ),

            generated_at=(
                _parse_datetime(
                    data.get(
                        "generated_at"
                    )
                )
                or datetime.now(
                    timezone.utc
                )
            ),

            engine_name=_text(
                raw_engine.get("name")
                or data.get(
                    "engine_name"
                )
                or (
                    "SS4TS Prediction "
                    "Engine"
                )
            ),

            engine_version=_text(
                raw_engine.get(
                    "version"
                )
                or data.get(
                    "engine_version"
                )
                or "1.6"
            ),

            predictions=[
                Prediction.from_dict(
                    item
                )
                for item in (
                    raw_predictions
                    if isinstance(
                        raw_predictions,
                        list,
                    )
                    else []
                )
                if isinstance(
                    item,
                    dict,
                )
            ],

            summary=_text(
                data.get("summary")
                or data.get(
                    "executive_summary"
                )
            ),

            analysis_context=(
                dict(
                    data.get(
                        "analysis_context",
                        data.get(
                            "request_context",
                            {},
                        ),
                    )
                )
                if isinstance(
                    data.get(
                        "analysis_context",
                        data.get(
                            "request_context",
                            {},
                        ),
                    ),
                    dict,
                )
                else {}
            ),

            data_sources=(
                dict(
                    data.get(
                        "data_sources",
                        {},
                    )
                )
                if isinstance(
                    data.get(
                        "data_sources",
                        {},
                    ),
                    dict,
                )
                else {}
            ),

            metadata=(
                dict(
                    data.get(
                        "metadata",
                        {},
                    )
                )
                if isinstance(
                    data.get(
                        "metadata",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        top_prediction = (
            self.top_prediction
        )

        return {
            "router_ip":
                self.router_ip,

            "device_name":
                self.device_name,

            "generated_at":
                _datetime_to_iso(
                    self.generated_at
                ),

            "engine": {
                "name":
                    self.engine_name,

                "version":
                    self.engine_version,

                "mode": (
                    "explainable-"
                    "predictive-analytics"
                ),
            },

            "overall_risk":
                self.overall_risk.value,

            "summary":
                self.summary,

            "top_prediction": (
                top_prediction.to_dict()
                if top_prediction
                else None
            ),

            "predictions": [
                item.to_dict()
                for item
                in self.predictions
            ],

            "statistics":
                self.statistics,

            "analysis_context":
                self.analysis_context,

            "data_sources":
                self.data_sources,

            "metadata":
                self.metadata,
        }


def normalize_predictions(
    predictions: list[
        dict[str, Any]
    ] | None,
) -> list[Prediction]:
    return [
        Prediction.from_dict(
            item
        )
        for item in (
            predictions or []
        )
        if isinstance(
            item,
            dict,
        )
    ]
