from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class HealthState(StrEnum):
    EXCELLENT = "excellent"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class TrendState(StrEnum):
    RISING = "rising"
    STABLE = "stable"
    FALLING = "falling"
    UNKNOWN = "unknown"


class FindingSeverity(StrEnum):
    HEALTHY = "healthy"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class IntelligenceFinding:
    code: str
    title: str
    severity: FindingSeverity
    message: str
    metric: str | None = None
    value: Any = None
    threshold: Any = None
    recommendation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "severity": self.severity.value,
            "message": self.message,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "recommendation": self.recommendation,
        }


@dataclass(slots=True)
class ComponentAnalysis:
    name: str
    available: bool
    score: int
    health: HealthState
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.score = max(0, min(int(self.score), 100))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "score": self.score,
            "health": self.health.value,
            "details": self.details,
        }


@dataclass(slots=True)
class NetworkIntelligenceAnalysis:
    overall_health_score: int
    overall_health: HealthState
    confidence_percent: int
    components: dict[str, ComponentAnalysis]
    findings: list[IntelligenceFinding] = field(
        default_factory=list
    )
    recommendations: list[str] = field(
        default_factory=list
    )
    analyzer_name: str = (
        "SS4TS Network Intelligence Analysis Engine"
    )
    analyzer_version: str = "1.0.0"

    def __post_init__(self) -> None:
        self.overall_health_score = max(
            0,
            min(int(self.overall_health_score), 100),
        )
        self.confidence_percent = max(
            0,
            min(int(self.confidence_percent), 100),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_health_score":
                self.overall_health_score,
            "overall_health":
                self.overall_health.value,
            "confidence_percent":
                self.confidence_percent,
            "components": {
                key: component.to_dict()
                for key, component
                in self.components.items()
            },
            "findings": [
                finding.to_dict()
                for finding in self.findings
            ],
            "recommendations": list(
                self.recommendations
            ),
            "analyzer": {
                "name": self.analyzer_name,
                "version": self.analyzer_version,
            },
        }
