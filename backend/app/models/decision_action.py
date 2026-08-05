from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class DecisionActionRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionActionExecutionMode(str, Enum):
    READ_ONLY = "read_only"
    DRY_RUN = "dry_run"
    MANUAL = "manual"
    APPROVAL_REQUIRED = "approval_required"
    AUTOMATIC = "automatic"


class DecisionActionStatus(str, Enum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class DecisionActionTarget:
    router_ip: str
    interface_name: str | None = None
    site_id: str | None = None
    device_id: str | None = None

    def __post_init__(self) -> None:
        self.router_ip = self.router_ip.strip()

        if not self.router_ip:
            raise ValueError(
                "Decision action target router_ip must not be empty"
            )

        if self.interface_name is not None:
            self.interface_name = (
                self.interface_name.strip()
                or None
            )

        if self.site_id is not None:
            self.site_id = (
                self.site_id.strip()
                or None
            )

        if self.device_id is not None:
            self.device_id = (
                self.device_id.strip()
                or None
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "router_ip": self.router_ip,
            "interface_name": self.interface_name,
            "site_id": self.site_id,
            "device_id": self.device_id,
        }


@dataclass(slots=True)
class DecisionActionCommand:
    action_type: str
    parameters: dict[str, Any] = field(
        default_factory=dict
    )
    rollback_action_type: str | None = None
    rollback_parameters: dict[str, Any] = field(
        default_factory=dict
    )
    verification_steps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.action_type = self.action_type.strip()

        if not self.action_type:
            raise ValueError(
                "Decision action type must not be empty"
            )

        if self.rollback_action_type is not None:
            self.rollback_action_type = (
                self.rollback_action_type.strip()
                or None
            )

        self.parameters = dict(
            self.parameters
        )

        self.rollback_parameters = dict(
            self.rollback_parameters
        )

        self.verification_steps = tuple(
            str(step).strip()
            for step in self.verification_steps
            if str(step).strip()
        )

    @property
    def is_reversible(self) -> bool:
        return bool(
            self.rollback_action_type
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "parameters": self.parameters,
            "rollback_action_type": (
                self.rollback_action_type
            ),
            "rollback_parameters": (
                self.rollback_parameters
            ),
            "verification_steps": list(
                self.verification_steps
            ),
            "is_reversible": self.is_reversible,
        }


@dataclass(slots=True)
class DecisionAction:
    decision_id: str
    incident_id: str | None
    problem: str
    recommendation: str
    confidence_percent: float
    risk_level: DecisionActionRiskLevel
    execution_mode: DecisionActionExecutionMode
    target: DecisionActionTarget
    command: DecisionActionCommand
    approval_required: bool
    requested_by: str
    status: DecisionActionStatus = (
        DecisionActionStatus.PROPOSED
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    created_at: datetime = field(
        default_factory=_utc_now
    )
    updated_at: datetime = field(
        default_factory=_utc_now
    )

    def __post_init__(self) -> None:
        self.decision_id = (
            self.decision_id.strip()
        )

        self.problem = self.problem.strip()
        self.recommendation = (
            self.recommendation.strip()
        )
        self.requested_by = (
            self.requested_by.strip()
        )

        if not self.decision_id:
            raise ValueError(
                "Decision ID must not be empty"
            )

        if not self.problem:
            raise ValueError(
                "Decision problem must not be empty"
            )

        if not self.recommendation:
            raise ValueError(
                "Decision recommendation must not be empty"
            )

        if not self.requested_by:
            raise ValueError(
                "Decision requester must not be empty"
            )

        if self.incident_id is not None:
            self.incident_id = (
                self.incident_id.strip()
                or None
            )

        self.confidence_percent = max(
            0.0,
            min(
                100.0,
                float(
                    self.confidence_percent
                ),
            ),
        )

        self.metadata = dict(
            self.metadata
        )

        if (
            self.risk_level
            in {
                DecisionActionRiskLevel.HIGH,
                DecisionActionRiskLevel.CRITICAL,
            }
            and not self.approval_required
        ):
            raise ValueError(
                "High-risk and critical actions "
                "must require approval"
            )

        if (
            self.execution_mode
            is DecisionActionExecutionMode.AUTOMATIC
            and self.approval_required
        ):
            raise ValueError(
                "Automatic execution cannot require "
                "pending human approval"
            )

        if (
            self.execution_mode
            is DecisionActionExecutionMode.AUTOMATIC
            and self.risk_level
            is not DecisionActionRiskLevel.LOW
        ):
            raise ValueError(
                "Only low-risk actions may use "
                "automatic execution"
            )

        if (
            self.risk_level
            in {
                DecisionActionRiskLevel.HIGH,
                DecisionActionRiskLevel.CRITICAL,
            }
            and not self.command.is_reversible
        ):
            raise ValueError(
                "High-risk and critical actions "
                "must define rollback"
            )

        if (
            self.execution_mode
            is DecisionActionExecutionMode.READ_ONLY
            and self.command.rollback_action_type
            is not None
        ):
            raise ValueError(
                "Read-only actions must not define rollback"
            )

    @classmethod
    def create(
        cls,
        *,
        incident_id: str | None,
        problem: str,
        recommendation: str,
        confidence_percent: float,
        risk_level: DecisionActionRiskLevel,
        execution_mode: DecisionActionExecutionMode,
        target: DecisionActionTarget,
        command: DecisionActionCommand,
        approval_required: bool,
        requested_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> "DecisionAction":
        now = _utc_now()

        return cls(
            decision_id=(
                f"decision:{uuid4()}"
            ),
            incident_id=incident_id,
            problem=problem,
            recommendation=recommendation,
            confidence_percent=confidence_percent,
            risk_level=risk_level,
            execution_mode=execution_mode,
            target=target,
            command=command,
            approval_required=approval_required,
            requested_by=requested_by,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "incident_id": self.incident_id,
            "problem": self.problem,
            "recommendation": self.recommendation,
            "confidence_percent": (
                self.confidence_percent
            ),
            "risk_level": self.risk_level.value,
            "execution_mode": (
                self.execution_mode.value
            ),
            "approval_required": (
                self.approval_required
            ),
            "requested_by": self.requested_by,
            "status": self.status.value,
            "target": self.target.to_dict(),
            "command": self.command.to_dict(),
            "metadata": self.metadata,
            "created_at": (
                self.created_at.isoformat()
            ),
            "updated_at": (
                self.updated_at.isoformat()
            ),
        }
