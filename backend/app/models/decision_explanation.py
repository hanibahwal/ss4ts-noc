from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _text(value: Any) -> str:
    return str(value).strip()


def _confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(
        0.0,
        min(
            confidence,
            100.0,
        ),
    )

    return round(
        confidence,
        2,
    )


@dataclass(slots=True)
class EvidenceItem:
    source: str
    key: str
    value: str

    confidence: float = 100.0

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.source = _text(
            self.source
        )

        self.key = _text(
            self.key
        )

        self.value = _text(
            self.value
        )

        self.confidence = _confidence(
            self.confidence
        )

        if not self.source:
            raise ValueError(
                "Evidence source is required"
            )

        if not self.key:
            raise ValueError(
                "Evidence key is required"
            )

    def to_dict(
        self,
    ) -> dict:
        return {
            "source":
                self.source,
            "key":
                self.key,
            "value":
                self.value,
            "confidence":
                self.confidence,
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class ExplanationItem:
    title: str

    description: str

    confidence: float

    evidence: list[
        EvidenceItem
    ] = field(
        default_factory=list
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
        self.title = _text(
            self.title
        )

        self.description = _text(
            self.description
        )

        self.confidence = _confidence(
            self.confidence
        )

        self.evidence.sort(
            key=lambda item: (
                -item.confidence,
                item.key,
            )
        )

        if not self.title:
            raise ValueError(
                "Explanation title required"
            )

    def to_dict(
        self,
    ) -> dict:
        return {
            "title":
                self.title,
            "description":
                self.description,
            "confidence":
                self.confidence,
            "evidence":[
                item.to_dict()
                for item
                in self.evidence
            ],
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class DecisionExplanation:
    decision_id: str

    summary: str

    confidence: float

    why: list[
        ExplanationItem
    ] = field(
        default_factory=list
    )

    recommendations: list[
        str
    ] = field(
        default_factory=list
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
        self.decision_id = _text(
            self.decision_id
        )

        self.summary = _text(
            self.summary
        )

        self.confidence = _confidence(
            self.confidence
        )

        self.why.sort(
            key=lambda item: (
                -item.confidence,
                item.title,
            )
        )

        self.recommendations = [
            _text(item)
            for item
            in self.recommendations
            if _text(item)
        ]

        if not self.decision_id:
            raise ValueError(
                "Decision id required"
            )

    def to_dict(
        self,
    ) -> dict:
        return {
            "decision_id":
                self.decision_id,
            "summary":
                self.summary,
            "confidence":
                self.confidence,
            "why":[
                item.to_dict()
                for item
                in self.why
            ],
            "recommendations":
                self.recommendations,
            "metadata":
                dict(self.metadata),
        }
