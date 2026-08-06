from __future__ import annotations

import json
import os
import sqlite3

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from app.models.decision_action import (
    DecisionAction,
    DecisionActionCommand,
    DecisionActionExecutionMode,
    DecisionActionRiskLevel,
    DecisionActionStatus,
    DecisionActionTarget,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.services.decision_action_service import (
    DecisionActionService,
)


DEFAULT_DECISION_EXECUTION_RUNTIME_DATABASE = Path(
    "/var/lib/ss4ts-noc/"
    "decision-execution-runtime.db"
)


class DecisionExecutionRuntimeError(RuntimeError):
    """Base persistent runtime error."""


class DecisionExecutionRuntimeNotFound(
    DecisionExecutionRuntimeError
):
    """Raised when runtime execution state is missing."""


class DecisionExecutionRuntimeConflict(
    DecisionExecutionRuntimeError
):
    """Raised when a runtime record already exists."""


@dataclass(slots=True)
class DecisionExecutionRuntimeItem:
    action: DecisionAction
    plan: ExecutionPlan
    authorization_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization_id":
                self.authorization_id,
            "action":
                self.action.to_dict(),
            "plan":
                self.plan.to_dict(),
        }


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _datetime(
    value: Any,
) -> datetime:
    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    if not text:
        raise ValueError(
            "Runtime datetime must not be empty"
        )

    return datetime.fromisoformat(
        text.replace(
            "Z",
            "+00:00",
        )
    )


def _action_from_dict(
    data: dict[str, Any],
) -> DecisionAction:
    if not isinstance(data, dict):
        raise TypeError(
            "Decision action payload must be a dictionary"
        )

    target_data = data.get(
        "target",
        {},
    )

    command_data = data.get(
        "command",
        {},
    )

    if not isinstance(target_data, dict):
        raise TypeError(
            "Decision action target must be a dictionary"
        )

    if not isinstance(command_data, dict):
        raise TypeError(
            "Decision action command must be a dictionary"
        )

    return DecisionAction(
        decision_id=str(
            data.get("decision_id", "")
        ),
        incident_id=(
            str(data["incident_id"])
            if data.get("incident_id")
            is not None
            else None
        ),
        problem=str(
            data.get("problem", "")
        ),
        recommendation=str(
            data.get("recommendation", "")
        ),
        confidence_percent=float(
            data.get(
                "confidence_percent",
                0,
            )
        ),
        risk_level=DecisionActionRiskLevel(
            data.get(
                "risk_level",
                DecisionActionRiskLevel.LOW.value,
            )
        ),
        execution_mode=(
            DecisionActionExecutionMode(
                data.get(
                    "execution_mode",
                    DecisionActionExecutionMode
                    .DRY_RUN.value,
                )
            )
        ),
        target=DecisionActionTarget(
            router_ip=str(
                target_data.get(
                    "router_ip",
                    "",
                )
            ),
            interface_name=(
                target_data.get(
                    "interface_name"
                )
            ),
            site_id=target_data.get(
                "site_id"
            ),
            device_id=target_data.get(
                "device_id"
            ),
        ),
        command=DecisionActionCommand(
            action_type=str(
                command_data.get(
                    "action_type",
                    "",
                )
            ),
            parameters=dict(
                command_data.get(
                    "parameters",
                    {},
                )
            ),
            rollback_action_type=(
                command_data.get(
                    "rollback_action_type"
                )
            ),
            rollback_parameters=dict(
                command_data.get(
                    "rollback_parameters",
                    {},
                )
            ),
            verification_steps=tuple(
                command_data.get(
                    "verification_steps",
                    [],
                )
            ),
        ),
        approval_required=bool(
            data.get(
                "approval_required",
                False,
            )
        ),
        requested_by=str(
            data.get(
                "requested_by",
                "",
            )
        ),
        status=DecisionActionStatus(
            data.get(
                "status",
                DecisionActionStatus
                .PROPOSED.value,
            )
        ),
        metadata=dict(
            data.get(
                "metadata",
                {},
            )
        ),
        created_at=_datetime(
            data.get("created_at")
        ),
        updated_at=_datetime(
            data.get("updated_at")
        ),
    )


class DecisionExecutionRuntime:
    """
    Persistent DecisionAction and ExecutionPlan runtime.

    Runtime records are stored in SQLite so prepared executions survive
    API restarts and are visible to multiple application workers.
    """

    def __init__(
        self,
        database_path: str | Path | None = None,
    ) -> None:
        self._configured_database_path = (
            Path(database_path)
            if database_path is not None
            else None
        )

        self.action_service = (
            DecisionActionService()
        )

        self._lock = RLock()

    @property
    def database_path(self) -> Path:
        if (
            self._configured_database_path
            is not None
        ):
            return (
                self._configured_database_path
            )

        configured = os.getenv(
            "SS4TS_DECISION_RUNTIME_DB",
            str(
                DEFAULT_DECISION_EXECUTION_RUNTIME_DATABASE
            ),
        ).strip()

        if not configured:
            raise RuntimeError(
                "SS4TS_DECISION_RUNTIME_DB "
                "must not be empty"
            )

        return Path(configured)

    def _connect(
        self,
    ) -> sqlite3.Connection:
        database_path = self.database_path

        database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = sqlite3.connect(
            database_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.execute(
            "PRAGMA synchronous = NORMAL"
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return connection

    def initialize(self) -> None:
        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                decision_execution_runtime (
                    authorization_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,
                    action_payload TEXT NOT NULL,
                    plan_payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_decision_execution_runtime_decision
                ON decision_execution_runtime (
                    decision_id
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_decision_execution_runtime_plan
                ON decision_execution_runtime (
                    plan_id
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate(
        *,
        action: DecisionAction,
        plan: ExecutionPlan,
        authorization_id: str,
    ) -> str:
        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            raise ValueError(
                "authorization_id must not be empty"
            )

        if not isinstance(
            action,
            DecisionAction,
        ):
            raise TypeError(
                "action must be a DecisionAction"
            )

        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan must be an ExecutionPlan"
            )

        if (
            action.decision_id
            != plan.decision_id
        ):
            raise ValueError(
                "Action and plan decision_id must match"
            )

        return normalized

    @staticmethod
    def _item_from_row(
        row: sqlite3.Row,
    ) -> DecisionExecutionRuntimeItem:
        action_payload = json.loads(
            row["action_payload"]
        )

        plan_payload = json.loads(
            row["plan_payload"]
        )

        return DecisionExecutionRuntimeItem(
            authorization_id=(
                row["authorization_id"]
            ),
            action=_action_from_dict(
                action_payload
            ),
            plan=ExecutionPlan.from_dict(
                plan_payload
            ),
        )

    def register(
        self,
        *,
        action: DecisionAction,
        plan: ExecutionPlan,
        authorization_id: str,
    ) -> DecisionExecutionRuntimeItem:
        normalized = self._validate(
            action=action,
            plan=plan,
            authorization_id=
                authorization_id,
        )

        self.initialize()

        now = datetime.now().astimezone(
        ).isoformat()

        try:
            with self._lock:
                with closing(
                    self._connect()
                ) as connection:
                    connection.execute(
                        """
                        INSERT INTO
                        decision_execution_runtime (
                            authorization_id,
                            decision_id,
                            plan_id,
                            source_node_id,
                            action_payload,
                            plan_payload,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            normalized,
                            action.decision_id,
                            plan.plan_id,
                            plan.source_node_id,
                            _canonical_json(
                                action.to_dict()
                            ),
                            _canonical_json(
                                plan.to_dict()
                            ),
                            now,
                            now,
                        ),
                    )

                    connection.commit()
        except sqlite3.IntegrityError as exc:
            raise DecisionExecutionRuntimeConflict(
                "Decision execution runtime "
                "record already exists"
            ) from exc

        self.action_service._actions[
            action.decision_id
        ] = action

        return DecisionExecutionRuntimeItem(
            action=action,
            plan=plan,
            authorization_id=normalized,
        )

    def update(
        self,
        *,
        action: DecisionAction,
        plan: ExecutionPlan,
        authorization_id: str,
    ) -> DecisionExecutionRuntimeItem:
        normalized = self._validate(
            action=action,
            plan=plan,
            authorization_id=
                authorization_id,
        )

        self.initialize()

        now = datetime.now().astimezone(
        ).isoformat()

        with self._lock:
            with closing(
                self._connect()
            ) as connection:
                cursor = connection.execute(
                    """
                    UPDATE
                    decision_execution_runtime
                    SET
                        decision_id = ?,
                        plan_id = ?,
                        source_node_id = ?,
                        action_payload = ?,
                        plan_payload = ?,
                        updated_at = ?
                    WHERE authorization_id = ?
                    """,
                    (
                        action.decision_id,
                        plan.plan_id,
                        plan.source_node_id,
                        _canonical_json(
                            action.to_dict()
                        ),
                        _canonical_json(
                            plan.to_dict()
                        ),
                        now,
                        normalized,
                    ),
                )

                connection.commit()

        if cursor.rowcount != 1:
            raise DecisionExecutionRuntimeNotFound(
                "Prepared decision execution not found: "
                f"{normalized}"
            )

        self.action_service._actions[
            action.decision_id
        ] = action

        return DecisionExecutionRuntimeItem(
            action=action,
            plan=plan,
            authorization_id=normalized,
        )

    def get(
        self,
        authorization_id: str,
    ) -> DecisionExecutionRuntimeItem:
        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            raise ValueError(
                "authorization_id must not be empty"
            )

        self.initialize()

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM decision_execution_runtime
                WHERE authorization_id = ?
                """,
                (normalized,),
            ).fetchone()

        if row is None:
            raise DecisionExecutionRuntimeNotFound(
                "Prepared decision execution not found: "
                f"{normalized}"
            )

        item = self._item_from_row(
            row
        )

        # Restore the action into the service used by the bridge.
        self.action_service._actions[
            item.action.decision_id
        ] = item.action

        return item

    def remove(
        self,
        authorization_id: str,
    ) -> bool:
        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            return False

        self.initialize()

        with self._lock:
            with closing(
                self._connect()
            ) as connection:
                row = connection.execute(
                    """
                    SELECT decision_id
                    FROM decision_execution_runtime
                    WHERE authorization_id = ?
                    """,
                    (normalized,),
                ).fetchone()

                cursor = connection.execute(
                    """
                    DELETE FROM
                    decision_execution_runtime
                    WHERE authorization_id = ?
                    """,
                    (normalized,),
                )

                connection.commit()

        if row is not None:
            self.action_service._actions.pop(
                row["decision_id"],
                None,
            )

        return cursor.rowcount == 1

    def count(self) -> int:
        self.initialize()

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM decision_execution_runtime
                """
            ).fetchone()

        return int(row["total"])

    def readiness(self) -> dict[str, Any]:
        """
        Validate persistent runtime availability.

        This performs local SQLite coordination only. It does not load
        DecisionAction payloads, expose secrets, contact managed devices,
        or execute network commands.
        """
        database_path = self.database_path

        try:
            self.initialize()

            with closing(
                self._connect()
            ) as connection:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                row = connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM decision_execution_runtime
                    """
                ).fetchone()

                quick_check = connection.execute(
                    "PRAGMA quick_check"
                ).fetchone()

                connection.rollback()

            integrity = (
                str(quick_check[0])
                if quick_check is not None
                else "unknown"
            )

            return {
                "status": (
                    "ready"
                    if integrity == "ok"
                    else "degraded"
                ),
                "initialized": True,
                "database_reachable": True,
                "database_writable": True,
                "integrity": integrity,
                "record_count": int(
                    row["total"]
                ),
                "database_path": str(
                    database_path
                ),
                "persistent": True,
                "network_io_performed": False,
                "device_command_executed": False,
            }

        except Exception as exc:
            return {
                "status": "not_ready",
                "initialized": False,
                "database_reachable": False,
                "database_writable": False,
                "integrity": "unknown",
                "record_count": None,
                "database_path": str(
                    database_path
                ),
                "persistent": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "network_io_performed": False,
                "device_command_executed": False,
            }

    def clear(self) -> int:
        self.initialize()

        with self._lock:
            with closing(
                self._connect()
            ) as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM
                    decision_execution_runtime
                    """
                )

                connection.commit()

        self.action_service._actions.clear()

        return max(
            cursor.rowcount,
            0,
        )


runtime = DecisionExecutionRuntime()
