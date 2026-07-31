from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Any


class ExecutionPlanStatus(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ExecutionStepType(StrEnum):
    OBSERVE = "observe"
    VALIDATE = "validate"
    COMMAND = "command"
    WAIT = "wait"
    VERIFY = "verify"
    NOTIFY = "notify"
    APPROVAL = "approval"
    ROLLBACK = "rollback"
    CLOSE_INCIDENT = "close_incident"
    UNKNOWN = "unknown"


class ExecutionStepStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    BLOCKED = "blocked"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"
    UNKNOWN = "unknown"


class ExecutionSafetyLevel(StrEnum):
    READ_ONLY = "read_only"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"
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


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    return int(
        _number(
            value,
            default,
        )
    )


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
        "approved",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "off",
        "disabled",
        "inactive",
        "rejected",
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


def _enum_value(
    enum_type,
    value: Any,
    default,
):
    normalized = _text(
        value,
        default.value,
    ).lower().replace(
        "-",
        "_",
    )

    try:
        return enum_type(normalized)
    except ValueError:
        return default


@dataclass(slots=True)
class ExecutionPlanStep:
    step_id: str
    sequence: int
    step_type: ExecutionStepType
    title: str
    description: str

    status: ExecutionStepStatus = (
        ExecutionStepStatus.PENDING
    )

    safety_level: ExecutionSafetyLevel = (
        ExecutionSafetyLevel.READ_ONLY
    )

    command: str | None = None
    expected_result: str | None = None
    rollback_command: str | None = None

    timeout_seconds: int = 30
    estimated_seconds: int = 30

    requires_approval: bool = False
    reversible: bool = True
    automatic_allowed: bool = False

    depends_on: list[str] = field(
        default_factory=list
    )

    verification_step_ids: list[str] = field(
        default_factory=list
    )

    confidence_percent: float = 0.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.step_id = _text(
            self.step_id
        )

        self.sequence = _integer(
            self.sequence
        )

        self.step_type = _enum_value(
            ExecutionStepType,
            self.step_type,
            ExecutionStepType.UNKNOWN,
        )

        self.title = _text(
            self.title
        )

        self.description = _text(
            self.description
        )

        self.status = _enum_value(
            ExecutionStepStatus,
            self.status,
            ExecutionStepStatus.UNKNOWN,
        )

        self.safety_level = _enum_value(
            ExecutionSafetyLevel,
            self.safety_level,
            ExecutionSafetyLevel.UNKNOWN,
        )

        self.command = _optional_text(
            self.command
        )

        self.expected_result = _optional_text(
            self.expected_result
        )

        self.rollback_command = _optional_text(
            self.rollback_command
        )

        self.timeout_seconds = max(
            _integer(
                self.timeout_seconds,
                30,
            ),
            1,
        )

        self.estimated_seconds = max(
            _integer(
                self.estimated_seconds,
                30,
            ),
            0,
        )

        self.requires_approval = _boolean(
            self.requires_approval
        )

        self.reversible = _boolean(
            self.reversible,
            True,
        )

        self.automatic_allowed = _boolean(
            self.automatic_allowed
        )

        self.depends_on = list(
            dict.fromkeys(
                _text(item)
                for item in self.depends_on
                if _text(item)
            )
        )

        self.verification_step_ids = list(
            dict.fromkeys(
                _text(item)
                for item
                in self.verification_step_ids
                if _text(item)
            )
        )

        self.confidence_percent = _percent(
            self.confidence_percent
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.step_id:
            raise ValueError(
                "Execution step_id must not be empty"
            )

        if self.sequence < 1:
            raise ValueError(
                "Execution step sequence must be at least 1"
            )

        if not self.title:
            raise ValueError(
                "Execution step title must not be empty"
            )

        if not self.description:
            raise ValueError(
                "Execution step description must not be empty"
            )

        if (
            self.step_type
            == ExecutionStepType.COMMAND
            and not self.command
        ):
            raise ValueError(
                "Command execution step requires a command"
            )

        if (
            not self.reversible
            and self.rollback_command
        ):
            raise ValueError(
                "Non-reversible step cannot define rollback_command"
            )

        if (
            self.automatic_allowed
            and self.safety_level
            in {
                ExecutionSafetyLevel.HIGH_RISK,
                ExecutionSafetyLevel.CRITICAL,
            }
        ):
            raise ValueError(
                "High-risk or critical step cannot allow automatic execution"
            )

    @property
    def is_mutating(
        self,
    ) -> bool:
        return (
            self.step_type
            == ExecutionStepType.COMMAND
        )

    @property
    def is_safe_for_automatic_execution(
        self,
    ) -> bool:
        return (
            self.automatic_allowed
            and not self.requires_approval
            and self.safety_level
            in {
                ExecutionSafetyLevel.READ_ONLY,
                ExecutionSafetyLevel.LOW_RISK,
            }
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ExecutionPlanStep:
        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Execution step data must be a dictionary"
            )

        return cls(
            step_id=_text(
                data.get("step_id")
                or data.get("id")
            ),
            sequence=_integer(
                data.get(
                    "sequence",
                    data.get("order", 0),
                )
            ),
            step_type=_enum_value(
                ExecutionStepType,
                data.get("step_type")
                or data.get("type"),
                ExecutionStepType.UNKNOWN,
            ),
            title=_text(
                data.get("title")
            ),
            description=_text(
                data.get("description")
                or data.get("summary")
            ),
            status=_enum_value(
                ExecutionStepStatus,
                data.get("status"),
                ExecutionStepStatus.PENDING,
            ),
            safety_level=_enum_value(
                ExecutionSafetyLevel,
                data.get("safety_level")
                or data.get("risk"),
                ExecutionSafetyLevel.READ_ONLY,
            ),
            command=_optional_text(
                data.get("command")
            ),
            expected_result=_optional_text(
                data.get("expected_result")
            ),
            rollback_command=_optional_text(
                data.get("rollback_command")
            ),
            timeout_seconds=_integer(
                data.get(
                    "timeout_seconds",
                    30,
                )
            ),
            estimated_seconds=_integer(
                data.get(
                    "estimated_seconds",
                    30,
                )
            ),
            requires_approval=_boolean(
                data.get(
                    "requires_approval"
                )
            ),
            reversible=_boolean(
                data.get("reversible"),
                True,
            ),
            automatic_allowed=_boolean(
                data.get(
                    "automatic_allowed"
                )
            ),
            depends_on=[
                str(item)
                for item in data.get(
                    "depends_on",
                    [],
                )
            ],
            verification_step_ids=[
                str(item)
                for item in data.get(
                    "verification_step_ids",
                    [],
                )
            ],
            confidence_percent=_percent(
                data.get(
                    "confidence_percent",
                    data.get("confidence", 0),
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
            "step_id":
                self.step_id,
            "id":
                self.step_id,
            "sequence":
                self.sequence,
            "step_type":
                self.step_type.value,
            "type":
                self.step_type.value,
            "title":
                self.title,
            "description":
                self.description,
            "status":
                self.status.value,
            "safety_level":
                self.safety_level.value,
            "command":
                self.command,
            "expected_result":
                self.expected_result,
            "rollback_command":
                self.rollback_command,
            "timeout_seconds":
                self.timeout_seconds,
            "estimated_seconds":
                self.estimated_seconds,
            "requires_approval":
                self.requires_approval,
            "reversible":
                self.reversible,
            "automatic_allowed":
                self.automatic_allowed,
            "depends_on":
                list(self.depends_on),
            "verification_step_ids":
                list(
                    self.verification_step_ids
                ),
            "confidence_percent":
                self.confidence_percent,
            "confidence":
                self.confidence_percent,
            "is_mutating":
                self.is_mutating,
            "is_safe_for_automatic_execution":
                self.is_safe_for_automatic_execution,
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class ExecutionPlan:
    plan_id: str
    source_node_id: str
    decision_id: str
    title: str
    summary: str

    steps: list[
        ExecutionPlanStep
    ] = field(
        default_factory=list
    )

    status: ExecutionPlanStatus = (
        ExecutionPlanStatus.DRAFT
    )

    created_at: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
        )
    )

    requires_approval: bool = True
    approved: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None

    dry_run_only: bool = True
    automatic_execution_allowed: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.plan_id = _text(
            self.plan_id
        )

        self.source_node_id = _text(
            self.source_node_id
        )

        self.decision_id = _text(
            self.decision_id
        )

        self.title = _text(
            self.title
        )

        self.summary = _text(
            self.summary
        )

        self.status = _enum_value(
            ExecutionPlanStatus,
            self.status,
            ExecutionPlanStatus.UNKNOWN,
        )

        self.created_at = _datetime(
            self.created_at
        )

        self.requires_approval = _boolean(
            self.requires_approval,
            True,
        )

        self.approved = _boolean(
            self.approved
        )

        self.approved_by = _optional_text(
            self.approved_by
        )

        if self.approved_at is not None:
            self.approved_at = _datetime(
                self.approved_at
            )

        self.dry_run_only = _boolean(
            self.dry_run_only,
            True,
        )

        self.automatic_execution_allowed = _boolean(
            self.automatic_execution_allowed
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        self.steps.sort(
            key=lambda step: (
                step.sequence,
                step.step_id,
            )
        )

        step_ids = [
            step.step_id
            for step in self.steps
        ]

        sequences = [
            step.sequence
            for step in self.steps
        ]

        if not self.plan_id:
            raise ValueError(
                "Execution plan_id must not be empty"
            )

        if not self.source_node_id:
            raise ValueError(
                "Execution source_node_id must not be empty"
            )

        if not self.decision_id:
            raise ValueError(
                "Execution decision_id must not be empty"
            )

        if not self.title:
            raise ValueError(
                "Execution plan title must not be empty"
            )

        if not self.summary:
            raise ValueError(
                "Execution plan summary must not be empty"
            )

        if len(step_ids) != len(
            set(step_ids)
        ):
            raise ValueError(
                "Execution plan contains duplicate step ids"
            )

        if len(sequences) != len(
            set(sequences)
        ):
            raise ValueError(
                "Execution plan contains duplicate sequences"
            )

        known_step_ids = set(
            step_ids
        )

        for step in self.steps:
            unknown_dependencies = (
                set(step.depends_on)
                - known_step_ids
            )

            if unknown_dependencies:
                raise ValueError(
                    "Execution step contains unknown dependency"
                )

            if step.step_id in step.depends_on:
                raise ValueError(
                    "Execution step cannot depend on itself"
                )

        if self.approved and not self.approved_by:
            raise ValueError(
                "Approved execution plan requires approved_by"
            )

        if (
            self.automatic_execution_allowed
            and self.dry_run_only
        ):
            raise ValueError(
                "Dry-run-only plan cannot allow automatic execution"
            )

        if (
            self.automatic_execution_allowed
            and any(
                not step
                .is_safe_for_automatic_execution
                for step in self.steps
            )
        ):
            raise ValueError(
                "Execution plan contains steps unsafe for automatic execution"
            )

    @property
    def step_count(
        self,
    ) -> int:
        return len(self.steps)

    @property
    def mutating_step_count(
        self,
    ) -> int:
        return sum(
            1
            for step in self.steps
            if step.is_mutating
        )

    @property
    def estimated_seconds(
        self,
    ) -> int:
        return sum(
            step.estimated_seconds
            for step in self.steps
        )

    @property
    def approval_required(
        self,
    ) -> bool:
        return (
            self.requires_approval
            or any(
                step.requires_approval
                for step in self.steps
            )
        )

    @property
    def rollback_available(
        self,
    ) -> bool:
        mutating_steps = [
            step
            for step in self.steps
            if step.is_mutating
        ]

        if not mutating_steps:
            return False

        return all(
            step.reversible
            and bool(
                step.rollback_command
            )
            for step in mutating_steps
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> ExecutionPlan:
        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Execution plan data must be a dictionary"
            )

        raw_steps = data.get(
            "steps",
            [],
        )

        return cls(
            plan_id=_text(
                data.get("plan_id")
                or data.get("id")
            ),
            source_node_id=_text(
                data.get("source_node_id")
                or data.get("source")
            ),
            decision_id=_text(
                data.get("decision_id")
            ),
            title=_text(
                data.get("title")
            ),
            summary=_text(
                data.get("summary")
                or data.get("description")
            ),
            steps=[
                (
                    item
                    if isinstance(
                        item,
                        ExecutionPlanStep,
                    )
                    else ExecutionPlanStep.from_dict(
                        item
                    )
                )
                for item in raw_steps
                if isinstance(
                    item,
                    (
                        ExecutionPlanStep,
                        dict,
                    ),
                )
            ],
            status=_enum_value(
                ExecutionPlanStatus,
                data.get("status"),
                ExecutionPlanStatus.DRAFT,
            ),
            created_at=_datetime(
                data.get("created_at")
            ),
            requires_approval=_boolean(
                data.get(
                    "requires_approval"
                ),
                True,
            ),
            approved=_boolean(
                data.get("approved")
            ),
            approved_by=_optional_text(
                data.get("approved_by")
            ),
            approved_at=(
                _datetime(
                    data.get("approved_at")
                )
                if data.get("approved_at")
                else None
            ),
            dry_run_only=_boolean(
                data.get("dry_run_only"),
                True,
            ),
            automatic_execution_allowed=_boolean(
                data.get(
                    "automatic_execution_allowed"
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
            "plan_id":
                self.plan_id,
            "id":
                self.plan_id,
            "source_node_id":
                self.source_node_id,
            "decision_id":
                self.decision_id,
            "title":
                self.title,
            "summary":
                self.summary,
            "status":
                self.status.value,
            "created_at":
                self.created_at.isoformat(),
            "requires_approval":
                self.requires_approval,
            "approval_required":
                self.approval_required,
            "approved":
                self.approved,
            "approved_by":
                self.approved_by,
            "approved_at": (
                self.approved_at.isoformat()
                if self.approved_at
                else None
            ),
            "dry_run_only":
                self.dry_run_only,
            "automatic_execution_allowed":
                self.automatic_execution_allowed,
            "statistics": {
                "step_count":
                    self.step_count,
                "mutating_step_count":
                    self.mutating_step_count,
                "estimated_seconds":
                    self.estimated_seconds,
                "rollback_available":
                    self.rollback_available,
            },
            "steps": [
                step.to_dict()
                for step in self.steps
            ],
            "metadata":
                dict(self.metadata),
        }


def normalize_execution_plan(
    value: Any,
) -> ExecutionPlan | None:
    if isinstance(
        value,
        ExecutionPlan,
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return ExecutionPlan.from_dict(
            value
        )

    return None
