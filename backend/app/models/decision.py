from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from enum import StrEnum
from math import isfinite
from typing import Any


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    HEALTHY = "healthy"
    UNKNOWN = "unknown"


class SignalSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    MEDIUM = "medium"
    NOTICE = "notice"
    INFO = "info"
    HEALTHY = "healthy"
    UNKNOWN = "unknown"


class SignalCategory(StrEnum):
    CONNECTIVITY = "connectivity"
    AVAILABILITY = "availability"
    CPU = "cpu"
    MEMORY = "memory"
    STORAGE = "storage"
    TEMPERATURE = "temperature"
    INTERFACES = "interfaces"
    ERRORS = "errors"
    DROPS = "drops"
    UTILIZATION = "utilization"
    TRAFFIC = "traffic"
    CAPACITY = "capacity"
    FAILURE = "failure"
    CORRELATION = "correlation"
    ROOT_CAUSE = "root_cause"
    PREDICTION = "prediction"
    SECURITY = "security"
    ROUTING = "routing"
    WIRELESS = "wireless"
    LTE = "lte"
    VPN = "vpn"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class DecisionPriority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class RecommendationType(StrEnum):
    INVESTIGATE = "investigate"
    MONITOR = "monitor"
    CONFIGURE = "configure"
    REPAIR = "repair"
    REPLACE = "replace"
    UPGRADE = "upgrade"
    SCALE = "scale"
    OPTIMIZE = "optimize"
    FAILOVER = "failover"
    SECURITY = "security"
    NO_ACTION = "no_action"
    UNKNOWN = "unknown"


RISK_PRIORITY = {
    RiskLevel.CRITICAL: 5,
    RiskLevel.HIGH: 4,
    RiskLevel.MEDIUM: 3,
    RiskLevel.LOW: 2,
    RiskLevel.HEALTHY: 1,
    RiskLevel.UNKNOWN: 0,
}


SEVERITY_PRIORITY = {
    SignalSeverity.CRITICAL: 7,
    SignalSeverity.HIGH: 6,
    SignalSeverity.WARNING: 5,
    SignalSeverity.MEDIUM: 4,
    SignalSeverity.NOTICE: 3,
    SignalSeverity.INFO: 2,
    SignalSeverity.HEALTHY: 1,
    SignalSeverity.UNKNOWN: 0,
}


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
    value: float,
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


def _normalize_risk(
    value: Any,
) -> RiskLevel:
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
        "good": "low",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return RiskLevel(normalized)
    except ValueError:
        return RiskLevel.UNKNOWN


def _normalize_severity(
    value: Any,
) -> SignalSeverity:
    normalized = _text(
        value,
        SignalSeverity.UNKNOWN,
    ).lower()

    aliases = {
        "error": "high",
        "danger": "critical",
        "low": "notice",
        "normal": "healthy",
        "stable": "healthy",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return SignalSeverity(
            normalized
        )
    except ValueError:
        return SignalSeverity.UNKNOWN


def _normalize_category(
    value: Any,
) -> SignalCategory:
    normalized = _text(
        value,
        SignalCategory.UNKNOWN,
    ).lower()

    aliases = {
        "interface": "interfaces",
        "bandwidth": "traffic",
        "congestion": "capacity",
        "root-cause": "root_cause",
        "rootcause": "root_cause",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return SignalCategory(
            normalized
        )
    except ValueError:
        return SignalCategory.UNKNOWN


def _normalize_priority(
    value: Any,
) -> DecisionPriority:
    normalized = _text(
        value,
        DecisionPriority.LOW,
    ).lower()

    aliases = {
        "critical": "urgent",
        "warning": "medium",
        "info": "informational",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return DecisionPriority(
            normalized
        )
    except ValueError:
        return DecisionPriority.LOW


def _normalize_decision_status(
    value: Any,
) -> DecisionStatus:
    normalized = _text(
        value,
        DecisionStatus.PROPOSED,
    ).lower()

    try:
        return DecisionStatus(
            normalized
        )
    except ValueError:
        return DecisionStatus.PROPOSED


def _normalize_recommendation_type(
    value: Any,
) -> RecommendationType:
    normalized = _text(
        value,
        RecommendationType.UNKNOWN,
    ).lower()

    aliases = {
        "check": "investigate",
        "inspection": "investigate",
        "watch": "monitor",
        "change": "configure",
        "fix": "repair",
        "expansion": "scale",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return RecommendationType(
            normalized
        )
    except ValueError:
        return RecommendationType.UNKNOWN


@dataclass(slots=True)
class Evidence:
    """
    One explainable evidence item supporting a signal,
    root cause or engineering decision.
    """

    key: str
    value: Any

    label: str | None = None
    unit: str | None = None
    source: str | None = None

    timestamp: datetime | None = None

    weight: float = 1.0

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> Evidence:
        return cls(
            key=_text(
                data.get("key")
                or data.get("name")
                or "evidence"
            ),

            value=data.get("value"),

            label=_optional_text(
                data.get("label")
            ),

            unit=_optional_text(
                data.get("unit")
            ),

            source=_optional_text(
                data.get("source")
            ),

            timestamp=_parse_datetime(
                data.get("timestamp")
                or data.get("time")
            ),

            weight=max(
                0.0,
                _number(
                    data.get(
                        "weight",
                        1.0,
                    ),
                    1.0,
                ),
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
        result = asdict(self)

        result["timestamp"] = (
            _datetime_to_iso(
                self.timestamp
            )
        )

        return result


@dataclass(slots=True)
class DecisionSignal:
    """
    An explainable signal discovered by AI, health,
    correlation or prediction engines.
    """

    signal_id: str
    title: str
    description: str

    category: SignalCategory = (
        SignalCategory.UNKNOWN
    )

    severity: SignalSeverity = (
        SignalSeverity.UNKNOWN
    )

    risk: RiskLevel = (
        RiskLevel.UNKNOWN
    )

    confidence_percent: float = 0.0
    score: float = 0.0

    interface_name: str | None = None
    device_ip: str | None = None

    detected_at: datetime | None = None

    recommendation: str | None = None

    evidence: list[
        Evidence
    ] = field(
        default_factory=list
    )

    tags: list[str] = field(
        default_factory=list
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
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
            or self.severity
            in {
                SignalSeverity.CRITICAL,
                SignalSeverity.HIGH,
                SignalSeverity.WARNING,
                SignalSeverity.MEDIUM,
            }
        )

    @property
    def priority_score(self) -> float:
        risk_weight = (
            RISK_PRIORITY.get(
                self.risk,
                0,
            )
            * 15.0
        )

        severity_weight = (
            SEVERITY_PRIORITY.get(
                self.severity,
                0,
            )
            * 8.0
        )

        confidence_weight = (
            self.confidence_percent
            * 0.15
        )

        return round(
            risk_weight
            + severity_weight
            + confidence_weight
            + self.score * 0.1,
            2,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DecisionSignal:
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
        elif isinstance(
            raw_evidence,
            list,
        ):
            evidence = [
                Evidence.from_dict(
                    item
                )
                for item in raw_evidence
                if isinstance(
                    item,
                    dict,
                )
            ]
        else:
            evidence = []

        raw_tags = data.get(
            "tags",
            [],
        )

        tags = (
            [
                _text(item)
                for item in raw_tags
                if _text(item)
            ]
            if isinstance(
                raw_tags,
                list,
            )
            else []
        )

        severity = (
            _normalize_severity(
                data.get("severity")
            )
        )

        risk_value = data.get("risk")

        if isinstance(
            risk_value,
            dict,
        ):
            risk_value = (
                risk_value.get("level")
            )

        risk = _normalize_risk(
            risk_value
        )

        if (
            risk == RiskLevel.UNKNOWN
        ):
            risk = {
                SignalSeverity.CRITICAL:
                    RiskLevel.CRITICAL,
                SignalSeverity.HIGH:
                    RiskLevel.HIGH,
                SignalSeverity.WARNING:
                    RiskLevel.MEDIUM,
                SignalSeverity.MEDIUM:
                    RiskLevel.MEDIUM,
                SignalSeverity.NOTICE:
                    RiskLevel.LOW,
                SignalSeverity.INFO:
                    RiskLevel.LOW,
                SignalSeverity.HEALTHY:
                    RiskLevel.HEALTHY,
            }.get(
                severity,
                RiskLevel.UNKNOWN,
            )

        return cls(
            signal_id=_text(
                data.get("signal_id")
                or data.get("id")
                or "unknown-signal"
            ),

            title=_text(
                data.get("title")
                or "Unnamed signal"
            ),

            description=_text(
                data.get("description")
            ),

            category=_normalize_category(
                data.get("category")
            ),

            severity=severity,
            risk=risk,

            confidence_percent=_clamp(
                data.get(
                    "confidence_percent",
                    data.get(
                        "confidence",
                        0,
                    ),
                )
            ),

            score=_clamp(
                data.get("score", 0)
            ),

            interface_name=_optional_text(
                data.get(
                    "interface_name"
                )
                or data.get(
                    "interface"
                )
            ),

            device_ip=_optional_text(
                data.get("device_ip")
                or data.get("router_ip")
            ),

            detected_at=_parse_datetime(
                data.get("detected_at")
                or data.get(
                    "generated_at"
                )
                or data.get("timestamp")
            ),

            recommendation=_optional_text(
                data.get(
                    "recommendation"
                )
            ),

            evidence=evidence,
            tags=tags,

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

        result["category"] = (
            self.category.value
        )

        result["severity"] = (
            self.severity.value
        )

        result["risk"] = (
            self.risk.value
        )

        result["detected_at"] = (
            _datetime_to_iso(
                self.detected_at
            )
        )

        result["evidence"] = [
            item.to_dict()
            for item in self.evidence
        ]

        result["is_actionable"] = (
            self.is_actionable
        )

        result["priority_score"] = (
            self.priority_score
        )

        result["id"] = (
            self.signal_id
        )

        result["confidence"] = (
            self.confidence_percent
        )

        return result


@dataclass(slots=True)
class RootCause:
    """
    Ranked probable cause supported by one or more signals.
    """

    cause_id: str
    title: str
    description: str

    category: SignalCategory = (
        SignalCategory.ROOT_CAUSE
    )

    risk: RiskLevel = (
        RiskLevel.UNKNOWN
    )

    confidence_percent: float = 0.0
    probability_percent: float = 0.0

    interface_name: str | None = None
    device_ip: str | None = None

    supporting_signal_ids: list[
        str
    ] = field(
        default_factory=list
    )

    evidence: list[
        Evidence
    ] = field(
        default_factory=list
    )

    alternative_causes: list[
        str
    ] = field(
        default_factory=list
    )

    recommendation: str | None = None

    @property
    def rank_score(self) -> float:
        return round(
            self.confidence_percent
            * 0.55
            + self.probability_percent
            * 0.35
            + RISK_PRIORITY.get(
                self.risk,
                0,
            )
            * 2.0,
            2,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> RootCause:
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

        signals = data.get(
            "supporting_signal_ids",
            data.get(
                "signals",
                [],
            ),
        )

        alternatives = data.get(
            "alternative_causes",
            [],
        )

        risk_value = data.get("risk")

        if isinstance(
            risk_value,
            dict,
        ):
            risk_value = (
                risk_value.get("level")
            )

        confidence = _clamp(
            data.get(
                "confidence_percent",
                data.get(
                    "confidence",
                    0,
                ),
            )
        )

        probability_value = (
            data.get(
                "probability_percent"
            )
        )

        probability = (
            confidence
            if probability_value is None
            else _clamp(
                probability_value
            )
        )

        return cls(
            cause_id=_text(
                data.get("cause_id")
                or data.get("id")
                or "unknown-cause"
            ),

            title=_text(
                data.get("title")
                or "Unknown cause"
            ),

            description=_text(
                data.get("description")
            ),

            category=_normalize_category(
                data.get(
                    "category",
                    "root_cause",
                )
            ),

            risk=_normalize_risk(
                risk_value
            ),

            confidence_percent=
                confidence,

            probability_percent=
                probability,

            interface_name=_optional_text(
                data.get(
                    "interface_name"
                )
            ),

            device_ip=_optional_text(
                data.get("device_ip")
                or data.get("router_ip")
            ),

            supporting_signal_ids=(
                [
                    _text(item)
                    for item in signals
                    if _text(item)
                ]
                if isinstance(
                    signals,
                    list,
                )
                else []
            ),

            evidence=evidence,

            alternative_causes=(
                [
                    _text(item)
                    for item
                    in alternatives
                    if _text(item)
                ]
                if isinstance(
                    alternatives,
                    list,
                )
                else []
            ),

            recommendation=_optional_text(
                data.get(
                    "recommendation"
                )
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        result = asdict(self)

        result["category"] = (
            self.category.value
        )

        result["risk"] = (
            self.risk.value
        )

        result["evidence"] = [
            item.to_dict()
            for item in self.evidence
        ]

        result["rank_score"] = (
            self.rank_score
        )

        result["id"] = (
            self.cause_id
        )

        result["confidence"] = (
            self.confidence_percent
        )

        return result


@dataclass(slots=True)
class Recommendation:
    """
    One engineering recommendation generated from signals
    and probable root causes.
    """

    recommendation_id: str
    title: str
    action: str

    recommendation_type: RecommendationType = (
        RecommendationType.UNKNOWN
    )

    priority: DecisionPriority = (
        DecisionPriority.LOW
    )

    reason: str | None = None
    expected_impact: str | None = None

    confidence_percent: float = 0.0

    interface_name: str | None = None
    device_ip: str | None = None

    related_signal_ids: list[
        str
    ] = field(
        default_factory=list
    )

    related_cause_ids: list[
        str
    ] = field(
        default_factory=list
    )

    requires_approval: bool = True
    is_reversible: bool | None = None

    estimated_minutes: int | None = None

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> Recommendation:
        signal_ids = data.get(
            "related_signal_ids",
            [],
        )

        cause_ids = data.get(
            "related_cause_ids",
            [],
        )

        return cls(
            recommendation_id=_text(
                data.get(
                    "recommendation_id"
                )
                or data.get("id")
                or "unknown-recommendation"
            ),

            title=_text(
                data.get("title")
                or "Recommendation"
            ),

            action=_text(
                data.get("action")
                or data.get(
                    "recommendation"
                )
            ),

            recommendation_type=(
                _normalize_recommendation_type(
                    data.get("type")
                    or data.get(
                        "recommendation_type"
                    )
                )
            ),

            priority=_normalize_priority(
                data.get("priority")
            ),

            reason=_optional_text(
                data.get("reason")
            ),

            expected_impact=(
                _optional_text(
                    data.get(
                        "expected_impact"
                    )
                )
            ),

            confidence_percent=_clamp(
                data.get(
                    "confidence_percent",
                    data.get(
                        "confidence",
                        0,
                    ),
                )
            ),

            interface_name=_optional_text(
                data.get(
                    "interface_name"
                )
            ),

            device_ip=_optional_text(
                data.get("device_ip")
                or data.get("router_ip")
            ),

            related_signal_ids=(
                [
                    _text(item)
                    for item in signal_ids
                    if _text(item)
                ]
                if isinstance(
                    signal_ids,
                    list,
                )
                else []
            ),

            related_cause_ids=(
                [
                    _text(item)
                    for item in cause_ids
                    if _text(item)
                ]
                if isinstance(
                    cause_ids,
                    list,
                )
                else []
            ),

            requires_approval=bool(
                data.get(
                    "requires_approval",
                    True,
                )
            ),

            is_reversible=(
                bool(
                    data.get(
                        "is_reversible"
                    )
                )
                if data.get(
                    "is_reversible"
                )
                is not None
                else None
            ),

            estimated_minutes=(
                max(
                    0,
                    _integer(
                        data.get(
                            "estimated_minutes"
                        )
                    ),
                )
                if data.get(
                    "estimated_minutes"
                )
                is not None
                else None
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        result = asdict(self)

        result[
            "recommendation_type"
        ] = (
            self.recommendation_type.value
        )

        result["priority"] = (
            self.priority.value
        )

        result["confidence"] = (
            self.confidence_percent
        )

        result["id"] = (
            self.recommendation_id
        )

        return result


@dataclass(slots=True)
class EngineeringDecision:
    """
    A proposed or executed engineering decision.
    """

    decision_id: str
    title: str
    action: str
    reason: str

    priority: DecisionPriority = (
        DecisionPriority.LOW
    )

    status: DecisionStatus = (
        DecisionStatus.PROPOSED
    )

    confidence_percent: float = 0.0

    expected_impact: str | None = None
    rollback_plan: str | None = None

    interface_name: str | None = None
    device_ip: str | None = None

    related_signal_ids: list[
        str
    ] = field(
        default_factory=list
    )

    related_cause_ids: list[
        str
    ] = field(
        default_factory=list
    )

    requires_approval: bool = True
    approved_by: str | None = None

    proposed_at: datetime | None = None
    executed_at: datetime | None = None
    completed_at: datetime | None = None

    execution_result: str | None = None

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> EngineeringDecision:
        signal_ids = data.get(
            "related_signal_ids",
            [],
        )

        cause_ids = data.get(
            "related_cause_ids",
            [],
        )

        return cls(
            decision_id=_text(
                data.get("decision_id")
                or data.get("id")
                or "unknown-decision"
            ),

            title=_text(
                data.get("title")
                or "Engineering decision"
            ),

            action=_text(
                data.get("action")
            ),

            reason=_text(
                data.get("reason")
            ),

            priority=_normalize_priority(
                data.get("priority")
            ),

            status=(
                _normalize_decision_status(
                    data.get("status")
                )
            ),

            confidence_percent=_clamp(
                data.get(
                    "confidence_percent",
                    data.get(
                        "confidence",
                        0,
                    ),
                )
            ),

            expected_impact=(
                _optional_text(
                    data.get(
                        "expected_impact"
                    )
                )
            ),

            rollback_plan=_optional_text(
                data.get(
                    "rollback_plan"
                )
            ),

            interface_name=_optional_text(
                data.get(
                    "interface_name"
                )
            ),

            device_ip=_optional_text(
                data.get("device_ip")
                or data.get("router_ip")
            ),

            related_signal_ids=(
                [
                    _text(item)
                    for item in signal_ids
                    if _text(item)
                ]
                if isinstance(
                    signal_ids,
                    list,
                )
                else []
            ),

            related_cause_ids=(
                [
                    _text(item)
                    for item in cause_ids
                    if _text(item)
                ]
                if isinstance(
                    cause_ids,
                    list,
                )
                else []
            ),

            requires_approval=bool(
                data.get(
                    "requires_approval",
                    True,
                )
            ),

            approved_by=_optional_text(
                data.get("approved_by")
            ),

            proposed_at=_parse_datetime(
                data.get("proposed_at")
                or data.get(
                    "generated_at"
                )
            ),

            executed_at=_parse_datetime(
                data.get("executed_at")
            ),

            completed_at=_parse_datetime(
                data.get("completed_at")
            ),

            execution_result=(
                _optional_text(
                    data.get(
                        "execution_result"
                    )
                )
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        result = asdict(self)

        result["priority"] = (
            self.priority.value
        )

        result["status"] = (
            self.status.value
        )

        result["confidence"] = (
            self.confidence_percent
        )

        result["proposed_at"] = (
            _datetime_to_iso(
                self.proposed_at
            )
        )

        result["executed_at"] = (
            _datetime_to_iso(
                self.executed_at
            )
        )

        result["completed_at"] = (
            _datetime_to_iso(
                self.completed_at
            )
        )

        result["id"] = (
            self.decision_id
        )

        return result


@dataclass(slots=True)
class DecisionIntelligenceResult:
    """
    Complete normalized output of the SS4TS Decision
    Intelligence Engine.
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
        "SS4TS Decision "
        "Intelligence Engine"
    )

    engine_version: str = "1.6"

    risk_level: RiskLevel = (
        RiskLevel.UNKNOWN
    )

    risk_score: float = 0.0

    executive_summary: str = ""

    signals: list[
        DecisionSignal
    ] = field(
        default_factory=list
    )

    root_causes: list[
        RootCause
    ] = field(
        default_factory=list
    )

    recommendations: list[
        Recommendation
    ] = field(
        default_factory=list
    )

    decisions: list[
        EngineeringDecision
    ] = field(
        default_factory=list
    )

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
        self.signals.sort(
            key=lambda item: (
                item.priority_score
            ),
            reverse=True,
        )

        self.root_causes.sort(
            key=lambda item: (
                item.rank_score
            ),
            reverse=True,
        )

        self.recommendations.sort(
            key=lambda item: {
                DecisionPriority.URGENT:
                    5,
                DecisionPriority.HIGH:
                    4,
                DecisionPriority.MEDIUM:
                    3,
                DecisionPriority.LOW:
                    2,
                DecisionPriority.INFORMATIONAL:
                    1,
            }.get(
                item.priority,
                0,
            ),
            reverse=True,
        )

        self.decisions.sort(
            key=lambda item: {
                DecisionPriority.URGENT:
                    5,
                DecisionPriority.HIGH:
                    4,
                DecisionPriority.MEDIUM:
                    3,
                DecisionPriority.LOW:
                    2,
                DecisionPriority.INFORMATIONAL:
                    1,
            }.get(
                item.priority,
                0,
            ),
            reverse=True,
        )

    @property
    def top_signal(
        self,
    ) -> DecisionSignal | None:
        if not self.signals:
            return None

        return self.signals[0]

    @property
    def primary_root_cause(
        self,
    ) -> RootCause | None:
        if not self.root_causes:
            return None

        return self.root_causes[0]

    @property
    def primary_recommendation(
        self,
    ) -> Recommendation | None:
        if not self.recommendations:
            return None

        return self.recommendations[0]

    @property
    def primary_decision(
        self,
    ) -> EngineeringDecision | None:
        if not self.decisions:
            return None

        return self.decisions[0]

    @property
    def actionable_signal_count(
        self,
    ) -> int:
        return sum(
            1
            for signal
            in self.signals
            if signal.is_actionable
        )

    @property
    def critical_signal_count(
        self,
    ) -> int:
        return sum(
            1
            for signal
            in self.signals
            if signal.risk
            == RiskLevel.CRITICAL
        )

    @property
    def high_signal_count(
        self,
    ) -> int:
        return sum(
            1
            for signal
            in self.signals
            if signal.risk
            == RiskLevel.HIGH
        )

    @property
    def statistics(
        self,
    ) -> dict[str, Any]:
        return {
            "signal_count":
                len(self.signals),

            "actionable_signal_count":
                self.actionable_signal_count,

            "critical_signal_count":
                self.critical_signal_count,

            "high_signal_count":
                self.high_signal_count,

            "root_cause_count":
                len(
                    self.root_causes
                ),

            "recommendation_count":
                len(
                    self.recommendations
                ),

            "decision_count":
                len(
                    self.decisions
                ),
        }

    @property
    def explainability(
        self,
    ) -> dict[str, Any]:
        top_signal = self.top_signal
        root_cause = (
            self.primary_root_cause
        )

        return {
            "risk_level":
                self.risk_level.value,

            "risk_score":
                self.risk_score,

            "top_signal": (
                top_signal.to_dict()
                if top_signal
                else None
            ),

            "primary_root_cause": (
                root_cause.to_dict()
                if root_cause
                else None
            ),

            "evidence_count": sum(
                len(signal.evidence)
                for signal
                in self.signals
            )
            + sum(
                len(cause.evidence)
                for cause
                in self.root_causes
            ),
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DecisionIntelligenceResult:
        risk_value = data.get(
            "risk"
        )

        if isinstance(
            risk_value,
            dict,
        ):
            risk_level = (
                risk_value.get("level")
            )

            risk_score = (
                risk_value.get("score")
            )
        else:
            risk_level = risk_value
            risk_score = data.get(
                "risk_score"
            )

        raw_engine = data.get(
            "engine",
            {},
        )

        if not isinstance(
            raw_engine,
            dict,
        ):
            raw_engine = {}

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
                    "SS4TS Decision "
                    "Intelligence Engine"
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

            risk_level=_normalize_risk(
                risk_level
            ),

            risk_score=_clamp(
                risk_score or 0
            ),

            executive_summary=_text(
                data.get(
                    "executive_summary"
                )
                or data.get("summary")
            ),

            signals=[
                DecisionSignal.from_dict(
                    item
                )
                for item in data.get(
                    "signals",
                    [],
                )
                if isinstance(
                    item,
                    dict,
                )
            ],

            root_causes=[
                RootCause.from_dict(
                    item
                )
                for item in data.get(
                    "root_causes",
                    [],
                )
                if isinstance(
                    item,
                    dict,
                )
            ],

            recommendations=[
                Recommendation.from_dict(
                    item
                )
                for item in data.get(
                    "recommendations",
                    [],
                )
                if isinstance(
                    item,
                    dict,
                )
            ],

            decisions=[
                EngineeringDecision.from_dict(
                    item
                )
                for item in data.get(
                    "decisions",
                    [],
                )
                if isinstance(
                    item,
                    dict,
                )
            ],

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
        top_signal = self.top_signal

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
                    "decision-intelligence"
                ),
            },

            "risk": {
                "level":
                    self.risk_level.value,

                "score":
                    round(
                        self.risk_score,
                        2,
                    ),
            },

            "executive_summary":
                self.executive_summary,

            "top_signal": (
                top_signal.to_dict()
                if top_signal
                else None
            ),

            "signals": [
                item.to_dict()
                for item
                in self.signals
            ],

            "root_causes": [
                item.to_dict()
                for item
                in self.root_causes
            ],

            "recommendations": [
                item.to_dict()
                for item
                in self.recommendations
            ],

            "decisions": [
                item.to_dict()
                for item
                in self.decisions
            ],

            "statistics":
                self.statistics,

            "explainability":
                self.explainability,

            "analysis_context":
                self.analysis_context,

            "data_sources":
                self.data_sources,

            "metadata":
                self.metadata,
        }


def normalize_signals(
    signals: list[
        dict[str, Any]
    ] | None,
) -> list[DecisionSignal]:
    return [
        DecisionSignal.from_dict(
            item
        )
        for item in (
            signals or []
        )
        if isinstance(
            item,
            dict,
        )
    ]


def normalize_root_causes(
    causes: list[
        dict[str, Any]
    ] | None,
) -> list[RootCause]:
    return [
        RootCause.from_dict(
            item
        )
        for item in (
            causes or []
        )
        if isinstance(
            item,
            dict,
        )
    ]


def normalize_recommendations(
    recommendations: list[
        dict[str, Any]
    ] | None,
) -> list[Recommendation]:
    return [
        Recommendation.from_dict(
            item
        )
        for item in (
            recommendations or []
        )
        if isinstance(
            item,
            dict,
        )
    ]


def normalize_decisions(
    decisions: list[
        dict[str, Any]
    ] | None,
) -> list[EngineeringDecision]:
    return [
        EngineeringDecision.from_dict(
            item
        )
        for item in (
            decisions or []
        )
        if isinstance(
            item,
            dict,
        )
    ]
