from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class SimulationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    BLOCKED = "blocked"


class SimulatedStepOutcome(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class SimulatedStepResult:
    step_id: str
    sequence: int
    title: str
    step_type: str

    outcome: SimulatedStepOutcome
    message: str

    started_at: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )
    completed_at: datetime | None = None

    duration_ms: float = 0.0
    rollback_attempted: bool = False
    rollback_succeeded: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.step_id = str(
            self.step_id
        ).strip()

        self.title = str(
            self.title
        ).strip()

        self.step_type = str(
            self.step_type
        ).strip()

        self.sequence = int(
            self.sequence
        )

        self.duration_ms = round(
            max(
                float(self.duration_ms),
                0.0,
            ),
            2,
        )

        if not isinstance(
            self.outcome,
            SimulatedStepOutcome,
        ):
            self.outcome = (
                SimulatedStepOutcome(
                    str(self.outcome)
                )
            )

        if not self.step_id:
            raise ValueError(
                "Simulation step_id must not be empty"
            )

        if self.sequence < 1:
            raise ValueError(
                "Simulation sequence must be at least 1"
            )

        if not self.title:
            raise ValueError(
                "Simulation step title must not be empty"
            )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "sequence": self.sequence,
            "title": self.title,
            "step_type": self.step_type,
            "outcome": self.outcome.value,
            "message": self.message,
            "started_at":
                self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
            "duration_ms":
                self.duration_ms,
            "rollback_attempted":
                self.rollback_attempted,
            "rollback_succeeded":
                self.rollback_succeeded,
            "metadata":
                dict(self.metadata),
        }


@dataclass(slots=True)
class ExecutionSimulationResult:
    simulation_id: str
    plan_id: str
    source_node_id: str

    status: SimulationStatus

    steps: list[
        SimulatedStepResult
    ] = field(
        default_factory=list
    )

    started_at: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )
    completed_at: datetime | None = None

    dry_run: bool = True
    approval_granted: bool = False
    rollback_performed: bool = False

    failure_step_id: str | None = None
    summary: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.simulation_id = str(
            self.simulation_id
        ).strip()

        self.plan_id = str(
            self.plan_id
        ).strip()

        self.source_node_id = str(
            self.source_node_id
        ).strip()

        if not isinstance(
            self.status,
            SimulationStatus,
        ):
            self.status = SimulationStatus(
                str(self.status)
            )

        self.steps.sort(
            key=lambda item: (
                item.sequence,
                item.step_id,
            )
        )

        if not self.simulation_id:
            raise ValueError(
                "Simulation id must not be empty"
            )

        if not self.plan_id:
            raise ValueError(
                "Simulation plan_id must not be empty"
            )

        if not self.source_node_id:
            raise ValueError(
                "Simulation source_node_id must not be empty"
            )

    @property
    def step_count(
        self,
    ) -> int:
        return len(self.steps)

    @property
    def successful_step_count(
        self,
    ) -> int:
        return sum(
            1
            for step in self.steps
            if step.outcome
            == SimulatedStepOutcome.SUCCESS
        )

    @property
    def failed_step_count(
        self,
    ) -> int:
        return sum(
            1
            for step in self.steps
            if step.outcome
            == SimulatedStepOutcome.FAILED
        )

    @property
    def blocked_step_count(
        self,
    ) -> int:
        return sum(
            1
            for step in self.steps
            if step.outcome
            == SimulatedStepOutcome.BLOCKED
        )

    @property
    def total_duration_ms(
        self,
    ) -> float:
        return round(
            sum(
                step.duration_ms
                for step in self.steps
            ),
            2,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "simulation_id":
                self.simulation_id,
            "plan_id":
                self.plan_id,
            "source_node_id":
                self.source_node_id,
            "status":
                self.status.value,
            "dry_run":
                self.dry_run,
            "approval_granted":
                self.approval_granted,
            "rollback_performed":
                self.rollback_performed,
            "failure_step_id":
                self.failure_step_id,
            "summary":
                self.summary,
            "started_at":
                self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
            "statistics": {
                "step_count":
                    self.step_count,
                "successful_step_count":
                    self.successful_step_count,
                "failed_step_count":
                    self.failed_step_count,
                "blocked_step_count":
                    self.blocked_step_count,
                "total_duration_ms":
                    self.total_duration_ms,
            },
            "steps": [
                step.to_dict()
                for step in self.steps
            ],
            "metadata":
                dict(self.metadata),
        }
