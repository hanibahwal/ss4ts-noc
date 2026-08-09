from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RollbackRequirement(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"


class RollbackReadiness(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    MISSING = "MISSING"
    READY = "READY"


class RollbackOutcome(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    STARTED = "STARTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ControlledRollbackContract:
    requirement: RollbackRequirement
    readiness: RollbackReadiness
    outcome: RollbackOutcome

    read_only: bool
    live_execution_allowed: bool = False
    device_command_executed: bool = False

    def __post_init__(self) -> None:
        if self.live_execution_allowed:
            raise ValueError(
                "H32.6 rollback contract cannot allow "
                "live rollback execution"
            )

        if self.device_command_executed:
            raise ValueError(
                "H32.6 rollback contract cannot claim "
                "device command execution"
            )

        if self.read_only:
            if (
                self.requirement
                != RollbackRequirement.NOT_REQUIRED
            ):
                raise ValueError(
                    "Read-only execution cannot require rollback"
                )

            if (
                self.readiness
                != RollbackReadiness.NOT_APPLICABLE
            ):
                raise ValueError(
                    "Read-only rollback readiness must be "
                    "NOT_APPLICABLE"
                )

            if (
                self.outcome
                != RollbackOutcome.NOT_ATTEMPTED
            ):
                raise ValueError(
                    "Read-only execution cannot attempt rollback"
                )

        if (
            self.requirement
            == RollbackRequirement.NOT_REQUIRED
            and self.readiness
            != RollbackReadiness.NOT_APPLICABLE
        ):
            raise ValueError(
                "Rollback not required must have "
                "NOT_APPLICABLE readiness"
            )

        if (
            self.requirement
            == RollbackRequirement.REQUIRED
            and self.readiness
            == RollbackReadiness.NOT_APPLICABLE
        ):
            raise ValueError(
                "Required rollback cannot be NOT_APPLICABLE"
            )

        if (
            self.outcome
            != RollbackOutcome.NOT_ATTEMPTED
            and self.readiness
            != RollbackReadiness.READY
        ):
            raise ValueError(
                "Rollback cannot start unless readiness is READY"
            )

    @property
    def rollback_required(self) -> bool:
        return (
            self.requirement
            == RollbackRequirement.REQUIRED
        )

    @property
    def rollback_ready(self) -> bool:
        return (
            self.readiness
            == RollbackReadiness.READY
        )

    @property
    def rollback_attempted(self) -> bool:
        return (
            self.outcome
            != RollbackOutcome.NOT_ATTEMPTED
        )

    @property
    def rollback_performed(self) -> bool:
        return self.outcome in {
            RollbackOutcome.VERIFIED,
            RollbackOutcome.FAILED,
        }

    @property
    def effective_status(self) -> str:
        if self.read_only:
            return "NOT_REQUIRED_READ_ONLY"

        if (
            self.requirement
            == RollbackRequirement.REQUIRED
            and self.readiness
            == RollbackReadiness.MISSING
        ):
            return "REQUIRED_MISSING"

        if self.outcome == RollbackOutcome.STARTED:
            return "STARTED"

        if self.outcome == RollbackOutcome.VERIFIED:
            return "VERIFIED"

        if self.outcome == RollbackOutcome.FAILED:
            return "FAILED"

        if self.readiness == RollbackReadiness.READY:
            return "READY"

        return "REQUIRED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement":
                self.requirement.value,
            "readiness":
                self.readiness.value,
            "outcome":
                self.outcome.value,
            "rollback_required":
                self.rollback_required,
            "rollback_ready":
                self.rollback_ready,
            "rollback_attempted":
                self.rollback_attempted,
            "rollback_performed":
                self.rollback_performed,
            "rollback_status":
                self.effective_status,
            "read_only":
                self.read_only,
            "live_execution_allowed":
                self.live_execution_allowed,
            "device_command_executed":
                self.device_command_executed,
        }


def read_only_rollback_contract(
) -> ControlledRollbackContract:
    return ControlledRollbackContract(
        requirement=(
            RollbackRequirement.NOT_REQUIRED
        ),
        readiness=(
            RollbackReadiness.NOT_APPLICABLE
        ),
        outcome=(
            RollbackOutcome.NOT_ATTEMPTED
        ),
        read_only=True,
    )


def mutating_rollback_contract(
    *,
    rollback_available: bool,
) -> ControlledRollbackContract:
    return ControlledRollbackContract(
        requirement=(
            RollbackRequirement.REQUIRED
        ),
        readiness=(
            RollbackReadiness.READY
            if rollback_available
            else RollbackReadiness.MISSING
        ),
        outcome=(
            RollbackOutcome.NOT_ATTEMPTED
        ),
        read_only=False,
    )
