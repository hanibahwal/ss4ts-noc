from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Any

from app.models.decision import (
    DecisionPriority,
    DecisionStatus,
    EngineeringDecision,
    Evidence,
    Recommendation,
    RootCause,
)
from app.models.knowledge_graph import (
    ImpactPath,
)


class ImpactSeverity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AffectedEntityType(StrEnum):
    SITE = "site"
    DEVICE = "device"
    INTERFACE = "interface"
    NETWORK_LINK = "network_link"
    CUSTOMER_SERVICE = "customer_service"
    VLAN = "vlan"
    ROUTE = "route"
    UNKNOWN = "unknown"


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


def _boolean(
    value: Any,
    default: bool = False,
) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    normalized = str(value).strip().lower()

    if normalized in {
        "true",
        "1",
        "yes",
        "on",
        "enabled",
        "available",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "off",
        "disabled",
        "unavailable",
    }:
        return False

    return default


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(number):
        return default

    return number


def _clamp_percent(
    value: Any,
) -> float:
    return round(
        max(
            0.0,
            min(
                _number(value),
                100.0,
            ),
        ),
        2,
    )


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if isinstance(value, datetime):
        return value

    text = _text(value)

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


def _datetime_to_iso(
    value: datetime | None,
) -> str | None:
    if value is None:
        return None

    return value.isoformat()


def _normalize_severity(
    value: Any,
) -> ImpactSeverity:
    normalized = _text(
        value,
        ImpactSeverity.UNKNOWN,
    ).lower().replace("-", "_")

    aliases = {
        "info": "informational",
        "warning": "medium",
        "major": "high",
        "urgent": "critical",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return ImpactSeverity(normalized)
    except ValueError:
        return ImpactSeverity.UNKNOWN


def _normalize_entity_type(
    value: Any,
) -> AffectedEntityType:
    normalized = _text(
        value,
        AffectedEntityType.UNKNOWN,
    ).lower().replace("-", "_")

    aliases = {
        "router": "device",
        "switch": "device",
        "access_point": "device",
        "ap": "device",
        "link": "network_link",
        "customer": "customer_service",
        "service": "customer_service",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return AffectedEntityType(
            normalized
        )
    except ValueError:
        return AffectedEntityType.UNKNOWN


@dataclass(slots=True)
class AffectedEntity:
    node_id: str
    label: str

    entity_type: AffectedEntityType = (
        AffectedEntityType.UNKNOWN
    )

    severity: ImpactSeverity = (
        ImpactSeverity.UNKNOWN
    )

    active: bool = True
    impact_score: float = 0.0

    reason: str | None = None
    site: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.node_id = _text(
            self.node_id
        )
        self.label = _text(
            self.label
        )

        self.entity_type = (
            _normalize_entity_type(
                self.entity_type
            )
        )

        self.severity = (
            _normalize_severity(
                self.severity
            )
        )

        self.active = _boolean(
            self.active,
            True,
        )

        self.impact_score = (
            _clamp_percent(
                self.impact_score
            )
        )

        self.reason = _optional_text(
            self.reason
        )
        self.site = _optional_text(
            self.site
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.node_id:
            raise ValueError(
                "AffectedEntity node_id "
                "must not be empty"
            )

        if not self.label:
            raise ValueError(
                "AffectedEntity label "
                "must not be empty"
            )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> AffectedEntity:
        if not isinstance(data, dict):
            raise TypeError(
                "AffectedEntity data must "
                "be a dictionary"
            )

        return cls(
            node_id=_text(
                data.get("node_id")
                or data.get("id")
            ),
            label=_text(
                data.get("label")
                or data.get("name")
                or data.get("node_id")
            ),
            entity_type=(
                _normalize_entity_type(
                    data.get("entity_type")
                    or data.get("type")
                )
            ),
            severity=_normalize_severity(
                data.get("severity")
            ),
            active=_boolean(
                data.get("active"),
                True,
            ),
            impact_score=_clamp_percent(
                data.get("impact_score")
                or data.get("score")
            ),
            reason=_optional_text(
                data.get("reason")
            ),
            site=_optional_text(
                data.get("site")
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

        result["entity_type"] = (
            self.entity_type.value
        )
        result["severity"] = (
            self.severity.value
        )
        result["id"] = self.node_id

        return result


@dataclass(slots=True)
class ImpactDecision:
    decision_id: str
    source_node_id: str
    title: str
    summary: str

    severity: ImpactSeverity = (
        ImpactSeverity.UNKNOWN
    )

    priority: DecisionPriority = (
        DecisionPriority.LOW
    )

    status: DecisionStatus = (
        DecisionStatus.PROPOSED
    )

    confidence_percent: float = 0.0

    affected_entities: list[
        AffectedEntity
    ] = field(
        default_factory=list
    )

    impact_paths: list[
        ImpactPath
    ] = field(
        default_factory=list
    )

    evidence: list[
        Evidence
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

    engineering_decisions: list[
        EngineeringDecision
    ] = field(
        default_factory=list
    )

    backup_available: bool = False
    requires_approval: bool = True

    generated_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.decision_id = _text(
            self.decision_id
        )
        self.source_node_id = _text(
            self.source_node_id
        )
        self.title = _text(
            self.title
        )
        self.summary = _text(
            self.summary
        )

        self.severity = (
            _normalize_severity(
                self.severity
            )
        )

        self.confidence_percent = (
            _clamp_percent(
                self.confidence_percent
            )
        )

        self.backup_available = (
            _boolean(
                self.backup_available,
                False,
            )
        )

        self.requires_approval = (
            _boolean(
                self.requires_approval,
                True,
            )
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.decision_id:
            raise ValueError(
                "ImpactDecision decision_id "
                "must not be empty"
            )

        if not self.source_node_id:
            raise ValueError(
                "ImpactDecision source_node_id "
                "must not be empty"
            )

        if not self.title:
            raise ValueError(
                "ImpactDecision title "
                "must not be empty"
            )

        if not self.summary:
            raise ValueError(
                "ImpactDecision summary "
                "must not be empty"
            )

        entity_ids = [
            item.node_id
            for item in self.affected_entities
        ]

        if len(entity_ids) != len(
            set(entity_ids)
        ):
            raise ValueError(
                "ImpactDecision contains "
                "duplicate affected node ids"
            )

        for path in self.impact_paths:
            if (
                path.source_id
                != self.source_node_id
            ):
                raise ValueError(
                    "Impact path must start "
                    "from source_node_id"
                )

    @property
    def affected_node_ids(
        self,
    ) -> list[str]:
        return [
            item.node_id
            for item in self.affected_entities
        ]

    @property
    def affected_count(
        self,
    ) -> int:
        return len(
            self.affected_entities
        )

    @property
    def highest_impact_score(
        self,
    ) -> float:
        return max(
            (
                item.impact_score
                for item
                in self.affected_entities
            ),
            default=0.0,
        )

    @property
    def primary_root_cause(
        self,
    ) -> RootCause | None:
        if not self.root_causes:
            return None

        return max(
            self.root_causes,
            key=lambda item: (
                item.rank_score
            ),
        )

    @property
    def primary_recommendation(
        self,
    ) -> Recommendation | None:
        if not self.recommendations:
            return None

        return self.recommendations[0]

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ImpactDecision:
        if not isinstance(data, dict):
            raise TypeError(
                "ImpactDecision data must "
                "be a dictionary"
            )

        return cls(
            decision_id=_text(
                data.get("decision_id")
                or data.get("id")
            ),
            source_node_id=_text(
                data.get("source_node_id")
                or data.get("source")
            ),
            title=_text(
                data.get("title")
                or "Impact decision"
            ),
            summary=_text(
                data.get("summary")
                or data.get("description")
            ),
            severity=_normalize_severity(
                data.get("severity")
            ),
            priority=data.get(
                "priority",
                DecisionPriority.LOW,
            ),
            status=data.get(
                "status",
                DecisionStatus.PROPOSED,
            ),
            confidence_percent=(
                _clamp_percent(
                    data.get(
                        "confidence_percent",
                        data.get(
                            "confidence",
                            0,
                        ),
                    )
                )
            ),
            affected_entities=[
                (
                    item
                    if isinstance(
                        item,
                        AffectedEntity,
                    )
                    else AffectedEntity.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "affected_entities",
                    data.get(
                        "affected_nodes",
                        [],
                    ),
                )
                if isinstance(
                    item,
                    (
                        AffectedEntity,
                        dict,
                    ),
                )
            ],
            impact_paths=[
                (
                    item
                    if isinstance(
                        item,
                        ImpactPath,
                    )
                    else ImpactPath.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "impact_paths",
                    [],
                )
                if isinstance(
                    item,
                    (
                        ImpactPath,
                        dict,
                    ),
                )
            ],
            evidence=[
                (
                    item
                    if isinstance(
                        item,
                        Evidence,
                    )
                    else Evidence.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "evidence",
                    [],
                )
                if isinstance(
                    item,
                    (
                        Evidence,
                        dict,
                    ),
                )
            ],
            root_causes=[
                (
                    item
                    if isinstance(
                        item,
                        RootCause,
                    )
                    else RootCause.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "root_causes",
                    [],
                )
                if isinstance(
                    item,
                    (
                        RootCause,
                        dict,
                    ),
                )
            ],
            recommendations=[
                (
                    item
                    if isinstance(
                        item,
                        Recommendation,
                    )
                    else Recommendation.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "recommendations",
                    data.get(
                        "recommended_actions",
                        [],
                    ),
                )
                if isinstance(
                    item,
                    (
                        Recommendation,
                        dict,
                    ),
                )
            ],
            engineering_decisions=[
                (
                    item
                    if isinstance(
                        item,
                        EngineeringDecision,
                    )
                    else EngineeringDecision.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "engineering_decisions",
                    data.get(
                        "decisions",
                        [],
                    ),
                )
                if isinstance(
                    item,
                    (
                        EngineeringDecision,
                        dict,
                    ),
                )
            ],
            backup_available=_boolean(
                data.get(
                    "backup_available"
                ),
                False,
            ),
            requires_approval=_boolean(
                data.get(
                    "requires_approval"
                ),
                True,
            ),
            generated_at=(
                _parse_datetime(
                    data.get("generated_at")
                )
                or datetime.now(
                    timezone.utc
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
        root_cause = (
            self.primary_root_cause
        )

        recommendation = (
            self.primary_recommendation
        )

        return {
            "decision_id":
                self.decision_id,
            "id":
                self.decision_id,
            "source_node_id":
                self.source_node_id,
            "title":
                self.title,
            "summary":
                self.summary,
            "severity":
                self.severity.value,
            "priority": (
                self.priority.value
                if hasattr(
                    self.priority,
                    "value",
                )
                else str(self.priority)
            ),
            "status": (
                self.status.value
                if hasattr(
                    self.status,
                    "value",
                )
                else str(self.status)
            ),
            "confidence_percent":
                self.confidence_percent,
            "confidence":
                self.confidence_percent,
            "affected_count":
                self.affected_count,
            "affected_node_ids":
                self.affected_node_ids,
            "affected_entities": [
                item.to_dict()
                for item
                in self.affected_entities
            ],
            "highest_impact_score":
                self.highest_impact_score,
            "impact_paths": [
                item.to_dict()
                for item
                in self.impact_paths
            ],
            "evidence": [
                item.to_dict()
                for item
                in self.evidence
            ],
            "root_causes": [
                item.to_dict()
                for item
                in self.root_causes
            ],
            "primary_root_cause": (
                root_cause.to_dict()
                if root_cause
                else None
            ),
            "recommendations": [
                item.to_dict()
                for item
                in self.recommendations
            ],
            "recommended_actions": [
                item.to_dict()
                for item
                in self.recommendations
            ],
            "primary_recommendation": (
                recommendation.to_dict()
                if recommendation
                else None
            ),
            "engineering_decisions": [
                item.to_dict()
                for item
                in self.engineering_decisions
            ],
            "backup_available":
                self.backup_available,
            "requires_approval":
                self.requires_approval,
            "generated_at":
                _datetime_to_iso(
                    self.generated_at
                ),
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class ImpactAnalysisResult:
    source_node_id: str

    decisions: list[
        ImpactDecision
    ] = field(
        default_factory=list
    )

    generated_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    engine_name: str = (
        "SS4TS Impact Intelligence Engine"
    )

    engine_version: str = "1.0"

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.source_node_id = _text(
            self.source_node_id
        )

        if not self.source_node_id:
            raise ValueError(
                "ImpactAnalysisResult "
                "source_node_id must not be empty"
            )

        self.decisions.sort(
            key=lambda item: (
                item.confidence_percent,
                item.highest_impact_score,
            ),
            reverse=True,
        )

    @property
    def decision_count(
        self,
    ) -> int:
        return len(self.decisions)

    @property
    def affected_node_ids(
        self,
    ) -> list[str]:
        result: list[str] = []

        for decision in self.decisions:
            for node_id in (
                decision.affected_node_ids
            ):
                if node_id not in result:
                    result.append(node_id)

        return result

    @property
    def affected_count(
        self,
    ) -> int:
        return len(
            self.affected_node_ids
        )

    @property
    def critical_decision_count(
        self,
    ) -> int:
        return sum(
            1
            for decision
            in self.decisions
            if decision.severity
            == ImpactSeverity.CRITICAL
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ImpactAnalysisResult:
        if not isinstance(data, dict):
            raise TypeError(
                "ImpactAnalysisResult data "
                "must be a dictionary"
            )

        return cls(
            source_node_id=_text(
                data.get("source_node_id")
                or data.get("source")
            ),
            decisions=[
                (
                    item
                    if isinstance(
                        item,
                        ImpactDecision,
                    )
                    else ImpactDecision.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "decisions",
                    [],
                )
                if isinstance(
                    item,
                    (
                        ImpactDecision,
                        dict,
                    ),
                )
            ],
            generated_at=(
                _parse_datetime(
                    data.get("generated_at")
                )
                or datetime.now(
                    timezone.utc
                )
            ),
            engine_name=_text(
                data.get("engine_name")
                or "SS4TS Impact "
                "Intelligence Engine"
            ),
            engine_version=_text(
                data.get("engine_version")
                or "1.0"
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
            "source_node_id":
                self.source_node_id,
            "generated_at":
                _datetime_to_iso(
                    self.generated_at
                ),
            "engine": {
                "name":
                    self.engine_name,
                "version":
                    self.engine_version,
                "mode":
                    "knowledge-graph-impact",
            },
            "statistics": {
                "decision_count":
                    self.decision_count,
                "affected_count":
                    self.affected_count,
                "critical_decision_count":
                    self.critical_decision_count,
            },
            "affected_node_ids":
                self.affected_node_ids,
            "decisions": [
                item.to_dict()
                for item
                in self.decisions
            ],
            "metadata":
                dict(self.metadata),
        }


def normalize_impact_decisions(
    values: Any,
) -> list[ImpactDecision]:
    if not isinstance(values, list):
        return []

    return [
        (
            item
            if isinstance(
                item,
                ImpactDecision,
            )
            else ImpactDecision.from_dict(
                item
            )
        )
        for item in values
        if isinstance(
            item,
            (
                ImpactDecision,
                dict,
            ),
        )
    ]
