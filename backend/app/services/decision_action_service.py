from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from app.models.decision_action import (
    DecisionAction,
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionStatus,
    DecisionActionTarget,
)


class DecisionActionServiceError(RuntimeError):
    """Base error for decision action service operations."""


class DecisionActionNotFound(DecisionActionServiceError):
    """Raised when a decision action does not exist."""


class DecisionActionConflict(DecisionActionServiceError):
    """Raised when an invalid state transition is requested."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DecisionActionService:
    """
    Builds and manages safe decision-action proposals.

    This service does not execute commands on network devices.
    It only validates, classifies and manages action state.
    """

    def __init__(self) -> None:
        self._actions: dict[str, DecisionAction] = {}

    @staticmethod
    def determine_approval_required(
        *,
        risk_level: DecisionActionRiskLevel,
        execution_mode: DecisionActionExecutionMode,
    ) -> bool:
        if risk_level in {
            DecisionActionRiskLevel.HIGH,
            DecisionActionRiskLevel.CRITICAL,
        }:
            return True

        if execution_mode in {
            DecisionActionExecutionMode.MANUAL,
            DecisionActionExecutionMode.APPROVAL_REQUIRED,
        }:
            return True

        return False

    @staticmethod
    def determine_initial_status(
        *,
        approval_required: bool,
        execution_mode: DecisionActionExecutionMode,
    ) -> DecisionActionStatus:
        if approval_required:
            return DecisionActionStatus.PENDING_APPROVAL

        if execution_mode in {
            DecisionActionExecutionMode.READ_ONLY,
            DecisionActionExecutionMode.DRY_RUN,
            DecisionActionExecutionMode.AUTOMATIC,
        }:
            return DecisionActionStatus.APPROVED

        return DecisionActionStatus.PROPOSED

    def create_action(
        self,
        *,
        incident_id: str | None,
        problem: str,
        recommendation: str,
        confidence_percent: float,
        risk_level: DecisionActionRiskLevel,
        execution_mode: DecisionActionExecutionMode,
        target: DecisionActionTarget,
        command: DecisionActionCommand,
        requested_by: str,
        metadata: dict[str, Any] | None = None,
        approval_required: bool | None = None,
    ) -> DecisionAction:
        resolved_approval_required = (
            approval_required
            if approval_required is not None
            else self.determine_approval_required(
                risk_level=risk_level,
                execution_mode=execution_mode,
            )
        )

        status = self.determine_initial_status(
            approval_required=resolved_approval_required,
            execution_mode=execution_mode,
        )

        action = DecisionAction.create(
            incident_id=incident_id,
            problem=problem,
            recommendation=recommendation,
            confidence_percent=confidence_percent,
            risk_level=risk_level,
            execution_mode=execution_mode,
            target=target,
            command=command,
            approval_required=resolved_approval_required,
            requested_by=requested_by,
            metadata=metadata,
        )

        action = replace(
            action,
            status=status,
        )

        self._actions[action.decision_id] = action

        return action

    def get_action(
        self,
        decision_id: str,
    ) -> DecisionAction:
        action = self._actions.get(
            decision_id
        )

        if action is None:
            raise DecisionActionNotFound(
                f"Decision action not found: {decision_id}"
            )

        return action

    def list_actions(
        self,
        *,
        status: DecisionActionStatus | None = None,
        risk_level: DecisionActionRiskLevel | None = None,
        incident_id: str | None = None,
    ) -> list[DecisionAction]:
        actions = list(
            self._actions.values()
        )

        if status is not None:
            actions = [
                action
                for action in actions
                if action.status is status
            ]

        if risk_level is not None:
            actions = [
                action
                for action in actions
                if action.risk_level is risk_level
            ]

        if incident_id is not None:
            actions = [
                action
                for action in actions
                if action.incident_id == incident_id
            ]

        return sorted(
            actions,
            key=lambda item: item.created_at,
            reverse=True,
        )

    def approve(
        self,
        decision_id: str,
        *,
        approved_by: str,
    ) -> DecisionAction:
        actor = approved_by.strip()

        if not actor:
            raise ValueError(
                "Approval actor must not be empty"
            )

        action = self.get_action(
            decision_id
        )

        if action.status is DecisionActionStatus.APPROVED:
            return action

        if action.status is not DecisionActionStatus.PENDING_APPROVAL:
            raise DecisionActionConflict(
                "Only pending decision actions may be approved"
            )

        now = _utc_now()

        metadata = {
            **action.metadata,
            "approved_by": actor,
            "approved_at": now.isoformat(),
        }

        updated = replace(
            action,
            status=DecisionActionStatus.APPROVED,
            metadata=metadata,
            updated_at=now,
        )

        self._actions[decision_id] = updated

        return updated

    def reject(
        self,
        decision_id: str,
        *,
        rejected_by: str,
        reason: str,
    ) -> DecisionAction:
        actor = rejected_by.strip()
        rejection_reason = reason.strip()

        if not actor:
            raise ValueError(
                "Rejection actor must not be empty"
            )

        if not rejection_reason:
            raise ValueError(
                "Rejection reason must not be empty"
            )

        action = self.get_action(
            decision_id
        )

        if action.status not in {
            DecisionActionStatus.PROPOSED,
            DecisionActionStatus.PENDING_APPROVAL,
            DecisionActionStatus.APPROVED,
        }:
            raise DecisionActionConflict(
                "Decision action cannot be rejected "
                f"from status '{action.status.value}'"
            )

        now = _utc_now()

        metadata = {
            **action.metadata,
            "rejected_by": actor,
            "rejected_at": now.isoformat(),
            "rejection_reason": rejection_reason,
        }

        updated = replace(
            action,
            status=DecisionActionStatus.REJECTED,
            metadata=metadata,
            updated_at=now,
        )

        self._actions[decision_id] = updated

        return updated

    def mark_executing(
        self,
        decision_id: str,
    ) -> DecisionAction:
        action = self.get_action(
            decision_id
        )

        if action.status is not DecisionActionStatus.APPROVED:
            raise DecisionActionConflict(
                "Only approved actions may enter execution"
            )

        now = _utc_now()

        updated = replace(
            action,
            status=DecisionActionStatus.EXECUTING,
            metadata={
                **action.metadata,
                "execution_started_at": now.isoformat(),
            },
            updated_at=now,
        )

        self._actions[decision_id] = updated

        return updated

    def mark_completed(
        self,
        decision_id: str,
        *,
        result: dict[str, Any] | None = None,
    ) -> DecisionAction:
        action = self.get_action(
            decision_id
        )

        if action.status is not DecisionActionStatus.EXECUTING:
            raise DecisionActionConflict(
                "Only executing actions may be completed"
            )

        now = _utc_now()

        updated = replace(
            action,
            status=DecisionActionStatus.COMPLETED,
            metadata={
                **action.metadata,
                "execution_completed_at": now.isoformat(),
                "execution_result": dict(
                    result or {}
                ),
            },
            updated_at=now,
        )

        self._actions[decision_id] = updated

        return updated

    def mark_failed(
        self,
        decision_id: str,
        *,
        error: str,
    ) -> DecisionAction:
        failure_error = error.strip()

        if not failure_error:
            raise ValueError(
                "Execution error must not be empty"
            )

        action = self.get_action(
            decision_id
        )

        if action.status is not DecisionActionStatus.EXECUTING:
            raise DecisionActionConflict(
                "Only executing actions may be marked failed"
            )

        now = _utc_now()

        updated = replace(
            action,
            status=DecisionActionStatus.FAILED,
            metadata={
                **action.metadata,
                "execution_failed_at": now.isoformat(),
                "execution_error": failure_error,
            },
            updated_at=now,
        )

        self._actions[decision_id] = updated

        return updated

    def cancel(
        self,
        decision_id: str,
        *,
        cancelled_by: str,
        reason: str,
    ) -> DecisionAction:
        actor = cancelled_by.strip()
        cancellation_reason = reason.strip()

        if not actor:
            raise ValueError(
                "Cancellation actor must not be empty"
            )

        if not cancellation_reason:
            raise ValueError(
                "Cancellation reason must not be empty"
            )

        action = self.get_action(
            decision_id
        )

        if action.status in {
            DecisionActionStatus.COMPLETED,
            DecisionActionStatus.FAILED,
            DecisionActionStatus.REJECTED,
            DecisionActionStatus.CANCELLED,
        }:
            raise DecisionActionConflict(
                "Completed or closed actions cannot be cancelled"
            )

        now = _utc_now()

        updated = replace(
            action,
            status=DecisionActionStatus.CANCELLED,
            metadata={
                **action.metadata,
                "cancelled_by": actor,
                "cancelled_at": now.isoformat(),
                "cancellation_reason": cancellation_reason,
            },
            updated_at=now,
        )

        self._actions[decision_id] = updated

        return updated
