from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from app.models.decision_action import (
    DecisionAction,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.services.decision_action_service import (
    DecisionActionService,
)


class DecisionExecutionRuntimeError(RuntimeError):
    """Base runtime registry error."""


class DecisionExecutionRuntimeNotFound(
    DecisionExecutionRuntimeError
):
    """Raised when runtime execution state is missing."""


@dataclass(slots=True)
class DecisionExecutionRuntimeItem:
    action: DecisionAction
    plan: ExecutionPlan
    authorization_id: str

    def to_dict(self) -> dict:
        return {
            "authorization_id":
                self.authorization_id,
            "action":
                self.action.to_dict(),
            "plan":
                self.plan.to_dict(),
        }


class DecisionExecutionRuntime:
    """
    Process-local registry for prepared decision executions.

    Persistent authorization, lease and evidence records remain in
    SQLite. This registry only preserves the Action and ExecutionPlan
    required by the current orchestration process.
    """

    def __init__(self) -> None:
        self.action_service = (
            DecisionActionService()
        )

        self._items: dict[
            str,
            DecisionExecutionRuntimeItem,
        ] = {}

        self._lock = RLock()

    def register(
        self,
        *,
        action: DecisionAction,
        plan: ExecutionPlan,
        authorization_id: str,
    ) -> DecisionExecutionRuntimeItem:
        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if (
            action.decision_id
            != plan.decision_id
        ):
            raise ValueError(
                "Action and plan decision_id must match"
            )

        item = DecisionExecutionRuntimeItem(
            action=action,
            plan=plan,
            authorization_id=normalized,
        )

        with self._lock:
            self._items[normalized] = item

        return item

    def get(
        self,
        authorization_id: str,
    ) -> DecisionExecutionRuntimeItem:
        normalized = str(
            authorization_id
        ).strip()

        with self._lock:
            item = self._items.get(
                normalized
            )

        if item is None:
            raise DecisionExecutionRuntimeNotFound(
                "Prepared decision execution not found: "
                f"{normalized}"
            )

        return item

    def remove(
        self,
        authorization_id: str,
    ) -> bool:
        normalized = str(
            authorization_id
        ).strip()

        with self._lock:
            return (
                self._items.pop(
                    normalized,
                    None,
                )
                is not None
            )

    def count(self) -> int:
        with self._lock:
            return len(self._items)


runtime = DecisionExecutionRuntime()
