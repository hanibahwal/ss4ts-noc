from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class DecisionTraceStageType(StrEnum):
    TELEMETRY = "telemetry"
    GRAPH_CONTEXT = "graph_context"
    ROOT_CAUSE = "root_cause"
    IMPACT = "impact"
    RESILIENCE = "resilience"
    DECISION_FUSION = "decision_fusion"
    EXPLANATION = "explanation"
    EXECUTION_PLAN = "execution_plan"
    SIMULATION = "simulation"
    VERIFICATION = "verification"
    UNKNOWN = "unknown"


class DecisionTraceStageStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    SELECTED = "selected"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    FAILED = "failed"
    UNKNOWN = "unknown"


def _text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    text = str(value).strip()

    return text or default


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
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
        "selected",
        "completed",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "off",
        "rejected",
        "failed",
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

    return datetime.now(
        timezone.utc
    )


def _stage_type(
    value: Any,
) -> DecisionTraceStageType:
    normalized = _text(
        value,
        DecisionTraceStageType.UNKNOWN,
    ).lower().replace("-", "_")

    try:
        return DecisionTraceStageType(
            normalized
        )
    except ValueError:
        return DecisionTraceStageType.UNKNOWN


def _stage_status(
    value: Any,
) -> DecisionTraceStageStatus:
    normalized = _text(
        value,
        DecisionTraceStageStatus.UNKNOWN,
    ).lower().replace("-", "_")

    try:
        return DecisionTraceStageStatus(
            normalized
        )
    except ValueError:
        return DecisionTraceStageStatus.UNKNOWN


@dataclass(slots=True)
class DecisionTraceStage:
    stage_id: str
    sequence: int
    stage_type: DecisionTraceStageType
    title: str
    description: str

    status: DecisionTraceStageStatus = (
        DecisionTraceStageStatus.COMPLETED
    )

    confidence_percent: float = 0.0
    selected: bool = False

    input_ids: list[str] = field(
        default_factory=list
    )

    output_ids: list[str] = field(
        default_factory=list
    )

    evidence_ids: list[str] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    def __post_init__(self) -> None:
        self.stage_id = _text(
            self.stage_id
        )

        self.sequence = int(
            _number(
                self.sequence,
                0,
            )
        )

        self.stage_type = _stage_type(
            self.stage_type
        )

        self.title = _text(
            self.title
        )

        self.description = _text(
            self.description
        )

        self.status = _stage_status(
            self.status
        )

        self.confidence_percent = (
            _percent(
                self.confidence_percent
            )
        )

        self.selected = _boolean(
            self.selected
        )

        self.input_ids = list(
            dict.fromkeys(
                _text(item)
                for item in self.input_ids
                if _text(item)
            )
        )

        self.output_ids = list(
            dict.fromkeys(
                _text(item)
                for item in self.output_ids
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

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        self.created_at = _datetime(
            self.created_at
        )

        if not self.stage_id:
            raise ValueError(
                "Decision trace stage_id must not be empty"
            )

        if self.sequence < 1:
            raise ValueError(
                "Decision trace sequence must be at least 1"
            )

        if not self.title:
            raise ValueError(
                "Decision trace title must not be empty"
            )

        if not self.description:
            raise ValueError(
                "Decision trace description must not be empty"
            )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DecisionTraceStage:
        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Decision trace stage data must be a dictionary"
            )

        return cls(
            stage_id=_text(
                data.get("stage_id")
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
            stage_type=_stage_type(
                data.get("stage_type")
                or data.get("type")
            ),
            title=_text(
                data.get("title")
            ),
            description=_text(
                data.get("description")
                or data.get("summary")
            ),
            status=_stage_status(
                data.get("status")
            ),
            confidence_percent=_percent(
                data.get(
                    "confidence_percent",
                    data.get("confidence", 0),
                )
            ),
            selected=_boolean(
                data.get("selected")
            ),
            input_ids=[
                str(item)
                for item in data.get(
                    "input_ids",
                    [],
                )
            ],
            output_ids=[
                str(item)
                for item in data.get(
                    "output_ids",
                    [],
                )
            ],
            evidence_ids=[
                str(item)
                for item in data.get(
                    "evidence_ids",
                    [],
                )
            ],
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
            created_at=_datetime(
                data.get("created_at")
            ),
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "stage_id":
                self.stage_id,
            "id":
                self.stage_id,
            "sequence":
                self.sequence,
            "stage_type":
                self.stage_type.value,
            "type":
                self.stage_type.value,
            "title":
                self.title,
            "description":
                self.description,
            "status":
                self.status.value,
            "confidence_percent":
                self.confidence_percent,
            "confidence":
                self.confidence_percent,
            "selected":
                self.selected,
            "input_ids":
                list(self.input_ids),
            "output_ids":
                list(self.output_ids),
            "evidence_ids":
                list(self.evidence_ids),
            "created_at":
                self.created_at.isoformat(),
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class DecisionTrace:
    trace_id: str
    decision_id: str
    source_node_id: str
    title: str

    stages: list[
        DecisionTraceStage
    ] = field(
        default_factory=list
    )

    generated_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    read_only: bool = True
    network_io_performed: bool = False
    device_command_executed: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.trace_id = _text(
            self.trace_id
        )

        self.decision_id = _text(
            self.decision_id
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

        self.read_only = _boolean(
            self.read_only,
            True,
        )

        self.network_io_performed = _boolean(
            self.network_io_performed
        )

        self.device_command_executed = _boolean(
            self.device_command_executed
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        self.stages.sort(
            key=lambda item: (
                item.sequence,
                item.stage_id,
            )
        )

        stage_ids = [
            stage.stage_id
            for stage in self.stages
        ]

        sequences = [
            stage.sequence
            for stage in self.stages
        ]

        if not self.trace_id:
            raise ValueError(
                "Decision trace_id must not be empty"
            )

        if not self.decision_id:
            raise ValueError(
                "Decision trace decision_id must not be empty"
            )

        if not self.source_node_id:
            raise ValueError(
                "Decision trace source_node_id must not be empty"
            )

        if not self.title:
            raise ValueError(
                "Decision trace title must not be empty"
            )

        if len(stage_ids) != len(
            set(stage_ids)
        ):
            raise ValueError(
                "Decision trace contains duplicate stage ids"
            )

        if len(sequences) != len(
            set(sequences)
        ):
            raise ValueError(
                "Decision trace contains duplicate sequences"
            )

        if (
            self.read_only
            and (
                self.network_io_performed
                or self.device_command_executed
            )
        ):
            raise ValueError(
                "Read-only decision trace cannot report execution"
            )

    @property
    def stage_count(
        self,
    ) -> int:
        return len(self.stages)

    @property
    def selected_stage_count(
        self,
    ) -> int:
        return sum(
            1
            for stage in self.stages
            if stage.selected
        )

    @property
    def final_stage(
        self,
    ) -> DecisionTraceStage | None:
        if not self.stages:
            return None

        return self.stages[-1]

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> DecisionTrace:
        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Decision trace data must be a dictionary"
            )

        return cls(
            trace_id=_text(
                data.get("trace_id")
                or data.get("id")
            ),
            decision_id=_text(
                data.get("decision_id")
            ),
            source_node_id=_text(
                data.get("source_node_id")
                or data.get("source")
            ),
            title=_text(
                data.get("title")
            ),
            stages=[
                (
                    item
                    if isinstance(
                        item,
                        DecisionTraceStage,
                    )
                    else DecisionTraceStage.from_dict(
                        item
                    )
                )
                for item in data.get(
                    "stages",
                    [],
                )
                if isinstance(
                    item,
                    (
                        DecisionTraceStage,
                        dict,
                    ),
                )
            ],
            generated_at=_datetime(
                data.get("generated_at")
            ),
            read_only=_boolean(
                data.get("read_only"),
                True,
            ),
            network_io_performed=_boolean(
                data.get(
                    "network_io_performed"
                )
            ),
            device_command_executed=_boolean(
                data.get(
                    "device_command_executed"
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
        final_stage = self.final_stage

        return {
            "trace_id":
                self.trace_id,
            "id":
                self.trace_id,
            "decision_id":
                self.decision_id,
            "source_node_id":
                self.source_node_id,
            "title":
                self.title,
            "generated_at":
                self.generated_at.isoformat(),
            "statistics": {
                "stage_count":
                    self.stage_count,
                "selected_stage_count":
                    self.selected_stage_count,
            },
            "stages": [
                stage.to_dict()
                for stage in self.stages
            ],
            "final_stage": (
                final_stage.to_dict()
                if final_stage
                else None
            ),
            "safety": {
                "read_only":
                    self.read_only,
                "network_io_performed":
                    self.network_io_performed,
                "device_command_executed":
                    self.device_command_executed,
            },
            "metadata":
                dict(self.metadata),
        }


def normalize_decision_trace(
    value: Any,
) -> DecisionTrace | None:
    if isinstance(
        value,
        DecisionTrace,
    ):
        return value

    if isinstance(value, dict):
        return DecisionTrace.from_dict(
            value
        )

    return None
