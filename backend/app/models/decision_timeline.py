from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Any


class TimelineEventType(StrEnum):
    OBSERVATION = "observation"
    EVIDENCE = "evidence"
    ROOT_CAUSE = "root_cause"
    IMPACT = "impact"
    BACKUP = "backup"
    RECOMMENDATION = "recommendation"
    DECISION = "decision"
    VERIFICATION = "verification"
    EXECUTION = "execution"
    ROLLBACK = "rollback"
    UNKNOWN = "unknown"


class TimelineEventStatus(StrEnum):
    INFORMATIONAL = "informational"
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    PROPOSED = "proposed"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
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


def _percent(
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
        "active",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "off",
        "disabled",
        "inactive",
    }:
        return False

    return default


def _datetime(
    value: Any,
) -> datetime:
    if isinstance(value, datetime):
        return value

    text = _text(value)

    if text:
        try:
            return datetime.fromisoformat(
                text.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            pass

    return datetime.now(timezone.utc)


def _event_type(
    value: Any,
) -> TimelineEventType:
    normalized = _text(
        value,
        TimelineEventType.UNKNOWN,
    ).lower().replace("-", "_")

    aliases = {
        "cause": "root_cause",
        "recommend": "recommendation",
        "action": "execution",
        "validate": "verification",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return TimelineEventType(normalized)
    except ValueError:
        return TimelineEventType.UNKNOWN


def _event_status(
    value: Any,
) -> TimelineEventStatus:
    normalized = _text(
        value,
        TimelineEventStatus.UNKNOWN,
    ).lower().replace("-", "_")

    aliases = {
        "info": "informational",
        "success": "completed",
        "error": "failed",
        "running": "executing",
    }

    normalized = aliases.get(
        normalized,
        normalized,
    )

    try:
        return TimelineEventStatus(normalized)
    except ValueError:
        return TimelineEventStatus.UNKNOWN


@dataclass(slots=True)
class DecisionTimelineEvent:
    event_id: str
    sequence: int
    event_type: TimelineEventType
    title: str
    description: str

    status: TimelineEventStatus = (
        TimelineEventStatus.INFORMATIONAL
    )

    timestamp: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    confidence_percent: float = 0.0

    source_id: str | None = None
    related_node_ids: list[str] = field(
        default_factory=list
    )

    evidence_ids: list[str] = field(
        default_factory=list
    )

    actionable: bool = False
    requires_approval: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.event_id = _text(
            self.event_id
        )
        self.title = _text(
            self.title
        )
        self.description = _text(
            self.description
        )

        self.sequence = int(
            _number(
                self.sequence,
                0,
            )
        )

        self.event_type = _event_type(
            self.event_type
        )
        self.status = _event_status(
            self.status
        )

        self.timestamp = _datetime(
            self.timestamp
        )

        self.confidence_percent = (
            _percent(
                self.confidence_percent
            )
        )

        self.source_id = _optional_text(
            self.source_id
        )

        self.related_node_ids = list(
            dict.fromkeys(
                _text(item)
                for item in self.related_node_ids
                if _text(item)
            )
        )

        self.evidence_ids = list(
            dict.fromkeys(
                _text(item)
                for item in self.evidence_ids
                if _text(item)
            )
        )

        self.actionable = _boolean(
            self.actionable,
            False,
        )

        self.requires_approval = _boolean(
            self.requires_approval,
            False,
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.event_id:
            raise ValueError(
                "Timeline event_id must not be empty"
            )

        if self.sequence < 1:
            raise ValueError(
                "Timeline sequence must be at least 1"
            )

        if not self.title:
            raise ValueError(
                "Timeline title must not be empty"
            )

        if not self.description:
            raise ValueError(
                "Timeline description must not be empty"
            )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DecisionTimelineEvent:
        if not isinstance(data, dict):
            raise TypeError(
                "Timeline event data must be a dictionary"
            )

        return cls(
            event_id=_text(
                data.get("event_id")
                or data.get("id")
            ),
            sequence=int(
                _number(
                    data.get(
                        "sequence",
                        data.get("order", 0),
                    )
                )
            ),
            event_type=_event_type(
                data.get("event_type")
                or data.get("type")
            ),
            title=_text(
                data.get("title")
            ),
            description=_text(
                data.get("description")
                or data.get("summary")
            ),
            status=_event_status(
                data.get("status")
            ),
            timestamp=_datetime(
                data.get("timestamp")
                or data.get("created_at")
            ),
            confidence_percent=_percent(
                data.get(
                    "confidence_percent",
                    data.get("confidence", 0),
                )
            ),
            source_id=_optional_text(
                data.get("source_id")
                or data.get("source")
            ),
            related_node_ids=[
                str(item)
                for item in data.get(
                    "related_node_ids",
                    data.get("nodes", []),
                )
            ],
            evidence_ids=[
                str(item)
                for item in data.get(
                    "evidence_ids",
                    [],
                )
            ],
            actionable=_boolean(
                data.get("actionable"),
                False,
            ),
            requires_approval=_boolean(
                data.get(
                    "requires_approval"
                ),
                False,
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
            "event_id":
                self.event_id,
            "id":
                self.event_id,
            "sequence":
                self.sequence,
            "event_type":
                self.event_type.value,
            "type":
                self.event_type.value,
            "title":
                self.title,
            "description":
                self.description,
            "status":
                self.status.value,
            "timestamp":
                self.timestamp.isoformat(),
            "confidence_percent":
                self.confidence_percent,
            "confidence":
                self.confidence_percent,
            "source_id":
                self.source_id,
            "related_node_ids":
                list(self.related_node_ids),
            "evidence_ids":
                list(self.evidence_ids),
            "actionable":
                self.actionable,
            "requires_approval":
                self.requires_approval,
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class DecisionTimeline:
    timeline_id: str
    source_node_id: str
    title: str

    events: list[
        DecisionTimelineEvent
    ] = field(
        default_factory=list
    )

    generated_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    decision_id: str | None = None
    explanation: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.timeline_id = _text(
            self.timeline_id
        )
        self.source_node_id = _text(
            self.source_node_id
        )
        self.title = _text(
            self.title
        )

        self.generated_at = _datetime(
            self.generated_at
        )

        self.decision_id = _optional_text(
            self.decision_id
        )
        self.explanation = _optional_text(
            self.explanation
        )

        self.events.sort(
            key=lambda item: (
                item.sequence,
                item.timestamp,
                item.event_id,
            )
        )

        event_ids = [
            event.event_id
            for event in self.events
        ]

        sequences = [
            event.sequence
            for event in self.events
        ]

        if not self.timeline_id:
            raise ValueError(
                "Timeline id must not be empty"
            )

        if not self.source_node_id:
            raise ValueError(
                "Timeline source_node_id must not be empty"
            )

        if not self.title:
            raise ValueError(
                "Timeline title must not be empty"
            )

        if len(event_ids) != len(
            set(event_ids)
        ):
            raise ValueError(
                "Timeline contains duplicate event ids"
            )

        if len(sequences) != len(
            set(sequences)
        ):
            raise ValueError(
                "Timeline contains duplicate sequences"
            )

    @property
    def event_count(
        self,
    ) -> int:
        return len(self.events)

    @property
    def actionable_event_count(
        self,
    ) -> int:
        return sum(
            1
            for event in self.events
            if event.actionable
        )

    @property
    def approval_required(
        self,
    ) -> bool:
        return any(
            event.requires_approval
            for event in self.events
        )

    @property
    def final_event(
        self,
    ) -> DecisionTimelineEvent | None:
        if not self.events:
            return None

        return self.events[-1]

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DecisionTimeline:
        if not isinstance(data, dict):
            raise TypeError(
                "Timeline data must be a dictionary"
            )

        return cls(
            timeline_id=_text(
                data.get("timeline_id")
                or data.get("id")
            ),
            source_node_id=_text(
                data.get("source_node_id")
                or data.get("source")
            ),
            title=_text(
                data.get("title")
            ),
            events=[
                (
                    item
                    if isinstance(
                        item,
                        DecisionTimelineEvent,
                    )
                    else DecisionTimelineEvent.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "events",
                    [],
                )
                if isinstance(
                    item,
                    (
                        DecisionTimelineEvent,
                        dict,
                    ),
                )
            ],
            generated_at=_datetime(
                data.get("generated_at")
            ),
            decision_id=_optional_text(
                data.get("decision_id")
            ),
            explanation=_optional_text(
                data.get("explanation")
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
        final_event = self.final_event

        return {
            "timeline_id":
                self.timeline_id,
            "id":
                self.timeline_id,
            "source_node_id":
                self.source_node_id,
            "decision_id":
                self.decision_id,
            "title":
                self.title,
            "explanation":
                self.explanation,
            "generated_at":
                self.generated_at.isoformat(),
            "statistics": {
                "event_count":
                    self.event_count,
                "actionable_event_count":
                    self.actionable_event_count,
                "approval_required":
                    self.approval_required,
            },
            "events": [
                event.to_dict()
                for event in self.events
            ],
            "final_event": (
                final_event.to_dict()
                if final_event
                else None
            ),
            "metadata":
                dict(self.metadata),
        }


def normalize_decision_timeline(
    value: Any,
) -> DecisionTimeline | None:
    if isinstance(
        value,
        DecisionTimeline,
    ):
        return value

    if isinstance(value, dict):
        return DecisionTimeline.from_dict(
            value
        )

    return None
