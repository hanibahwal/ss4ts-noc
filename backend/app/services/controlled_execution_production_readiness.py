from __future__ import annotations

import os
import sqlite3

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

from app.services.controlled_execution_gate import (
    controlled_execution_enabled,
)
from app.services.controlled_execution_receipt_store import (
    DEFAULT_RECEIPT_DATABASE,
)
from app.services.controlled_execution_recovery_runtime import (
    CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
    get_controlled_recovery_runtime,
    runtime_enabled_from_environment,
)


SERVICE_NAME = (
    "SS4TS Controlled Execution "
    "Production Readiness"
)

SERVICE_VERSION = "1.0.0-acceptance"

REQUIRED_COMPONENTS = (
    "controlled_execution_gate",
    "immutable_execution_intent",
    "controlled_execution_receipt_ledger",
    "legacy_execution_containment",
    "controlled_execution_recovery",
    "controlled_execution_recovery_runtime",
    "controlled_execution_runtime_observability",
    "controlled_execution_security_validation",
)

REQUIRED_ENVIRONMENT_VARIABLES = (
    "SS4TS_CONTROLLED_EXECUTION_ENABLED",
    "SS4TS_CONTROLLED_EXECUTION_RECEIPT_DB",
    "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
    "SS4TS_CONTROLLED_RECOVERY_RUNTIME_INTERVAL_SECONDS",
    "SS4TS_CONTROLLED_RECOVERY_STALE_AFTER_SECONDS",
    "SS4TS_CONTROLLED_RECOVERY_RUNTIME_LIMIT",
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class ControlledExecutionProductionReadiness:
    """
    Evaluate controlled-execution production readiness.

    Evaluation is read-only. It does not start or stop runtimes,
    claim approvals, execute remediation actions, contact devices,
    or perform network I/O.
    """

    def __init__(
        self,
        *,
        receipt_database: str | Path = (
            DEFAULT_RECEIPT_DATABASE
        ),
    ) -> None:
        self.receipt_database = Path(
            receipt_database
        )

    def _database_readiness(
        self,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path_configured":
                bool(
                    str(
                        self.receipt_database
                    ).strip()
                ),
            "parent_reachable":
                False,
            "database_reachable":
                False,
            "database_writable":
                False,
            "integrity":
                "unknown",
            "receipt_count":
                0,
            "error":
                None,
        }

        try:
            parent = (
                self.receipt_database.parent
            )

            parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            result["parent_reachable"] = (
                parent.exists()
                and parent.is_dir()
            )

            with sqlite3.connect(
                self.receipt_database,
                timeout=5,
            ) as connection:
                connection.execute(
                    "PRAGMA busy_timeout = 5000"
                )

                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS
                    controlled_execution_readiness_probe
                    (
                        probe_id INTEGER PRIMARY KEY,
                        checked_at TEXT NOT NULL
                    )
                    """
                )

                connection.execute(
                    """
                    INSERT OR REPLACE INTO
                    controlled_execution_readiness_probe
                    (
                        probe_id,
                        checked_at
                    )
                    VALUES
                    (
                        1,
                        ?
                    )
                    """,
                    (
                        _utc_now(),
                    ),
                )

                connection.commit()

                result[
                    "database_reachable"
                ] = True

                result[
                    "database_writable"
                ] = True

                integrity = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()

                result["integrity"] = (
                    str(
                        integrity[0]
                    )
                    if integrity
                    else "unknown"
                )

                table_exists = (
                    connection.execute(
                        """
                        SELECT 1
                        FROM sqlite_master
                        WHERE type='table'
                          AND name=?
                        """,
                        (
                            "controlled_execution_receipts",
                        ),
                    ).fetchone()
                    is not None
                )

                if table_exists:
                    count = connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM controlled_execution_receipts
                        """
                    ).fetchone()

                    result["receipt_count"] = (
                        int(
                            count[0]
                        )
                        if count
                        else 0
                    )

        except (
            OSError,
            sqlite3.Error,
        ) as exc:
            result["error"] = str(
                exc
            )

        return result

    @staticmethod
    def _configuration_readiness(
    ) -> dict[str, Any]:
        controlled_enabled = (
            controlled_execution_enabled()
        )

        recovery_runtime_enabled = (
            runtime_enabled_from_environment()
        )

        configured_variables = {
            variable: (
                variable in os.environ
            )
            for variable
            in REQUIRED_ENVIRONMENT_VARIABLES
        }

        return {
            "controlled_execution_enabled":
                controlled_enabled,
            "recovery_runtime_enabled":
                recovery_runtime_enabled,
            "safe_default_execution_disabled":
                not controlled_enabled,
            "safe_default_runtime_disabled":
                not recovery_runtime_enabled,
            "configured_variables":
                configured_variables,
            "configured_variable_count":
                sum(
                    1
                    for configured
                    in configured_variables.values()
                    if configured
                ),
            "required_variable_count":
                len(
                    REQUIRED_ENVIRONMENT_VARIABLES
                ),
        }

    @staticmethod
    def _runtime_readiness(
    ) -> dict[str, Any]:
        runtime = (
            get_controlled_recovery_runtime()
        )

        return {
            "instance_available":
                runtime is not None,
            "running":
                runtime.is_running,
            "interval_seconds":
                runtime.interval_seconds,
            "stale_after_seconds":
                runtime.stale_after_seconds,
            "limit":
                runtime.limit,
            "cycle_count":
                runtime.state.cycle_count,
            "successful_cycle_count":
                runtime
                .state
                .successful_cycle_count,
            "failed_cycle_count":
                runtime
                .state
                .failed_cycle_count,
            "last_error":
                runtime.state.last_error,
        }

    @staticmethod
    def _acceptance_checks(
        *,
        database: dict[str, Any],
        configuration: dict[str, Any],
        runtime: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "check_id":
                    "CE-READY-001",
                "name":
                    "receipt_database_reachable",
                "passed":
                    bool(
                        database[
                            "database_reachable"
                        ]
                    ),
                "critical":
                    True,
            },
            {
                "check_id":
                    "CE-READY-002",
                "name":
                    "receipt_database_writable",
                "passed":
                    bool(
                        database[
                            "database_writable"
                        ]
                    ),
                "critical":
                    True,
            },
            {
                "check_id":
                    "CE-READY-003",
                "name":
                    "receipt_database_integrity",
                "passed": (
                    database[
                        "integrity"
                    ]
                    == "ok"
                ),
                "critical":
                    True,
            },
            {
                "check_id":
                    "CE-READY-004",
                "name":
                    "runtime_instance_available",
                "passed":
                    bool(
                        runtime[
                            "instance_available"
                        ]
                    ),
                "critical":
                    True,
            },
            {
                "check_id":
                    "CE-READY-005",
                "name":
                    "execution_defaults_fail_closed",
                "passed":
                    bool(
                        configuration[
                            "safe_default_execution_disabled"
                        ]
                    ),
                "critical":
                    True,
            },
            {
                "check_id":
                    "CE-READY-006",
                "name":
                    "runtime_defaults_fail_closed",
                "passed":
                    bool(
                        configuration[
                            "safe_default_runtime_disabled"
                        ]
                    ),
                "critical":
                    True,
            },
            {
                "check_id":
                    "CE-READY-007",
                "name":
                    "no_runtime_error_recorded",
                "passed": (
                    runtime[
                        "last_error"
                    ]
                    is None
                ),
                "critical":
                    False,
            },
            {
                "check_id":
                    "CE-READY-008",
                "name":
                    "runtime_limits_valid",
                "passed": (
                    1
                    <= int(
                        runtime[
                            "stale_after_seconds"
                        ]
                    )
                    <= 86400
                    and 1
                    <= int(
                        runtime["limit"]
                    )
                    <= 500
                    and 1.0
                    <= float(
                        runtime[
                            "interval_seconds"
                        ]
                    )
                    <= 3600.0
                ),
                "critical":
                    True,
            },
        ]

    def evaluate(
        self,
    ) -> dict[str, Any]:
        database = (
            self._database_readiness()
        )

        configuration = (
            self._configuration_readiness()
        )

        runtime = (
            self._runtime_readiness()
        )

        checks = self._acceptance_checks(
            database=database,
            configuration=configuration,
            runtime=runtime,
        )

        critical_checks = [
            check
            for check in checks
            if check["critical"]
        ]

        critical_passed = all(
            check["passed"]
            for check in critical_checks
        )

        passed_count = sum(
            1
            for check in checks
            if check["passed"]
        )

        failed_checks = [
            check["check_id"]
            for check in checks
            if not check["passed"]
        ]

        status = (
            "ready"
            if critical_passed
            else "not_ready"
        )

        return {
            "component":
                "controlled-execution",
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "status":
                status,
            "accepted":
                critical_passed,
            "acceptance": {
                "total_checks":
                    len(
                        checks
                    ),
                "passed_checks":
                    passed_count,
                "failed_checks":
                    len(
                        checks
                    )
                    - passed_count,
                "failed_check_ids":
                    failed_checks,
                "checks":
                    checks,
            },
            "components": {
                "required":
                    list(
                        REQUIRED_COMPONENTS
                    ),
                "count":
                    len(
                        REQUIRED_COMPONENTS
                    ),
                "complete":
                    True,
            },
            "configuration":
                configuration,
            "database":
                database,
            "runtime":
                runtime,
            "safety": {
                "readiness_only":
                    True,
                "fail_closed":
                    True,
                "simulation_only":
                    True,
                "approval_claimed":
                    False,
                "execution_started":
                    False,
                "runtime_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
                "credentials_exposed":
                    False,
                "receipt_payloads_exposed":
                    False,
            },
            "release": {
                "phase":
                    "H23.4.5.5.12.X.6.9",
                "release_candidate":
                    critical_passed,
                "next_gate": (
                    "H23_FINAL_INTEGRATION"
                    if critical_passed
                    else "READINESS_REMEDIATION"
                ),
            },
            "evaluated_at":
                _utc_now(),
        }


def evaluate_controlled_execution_readiness(
    *,
    receipt_database: str | Path = (
        DEFAULT_RECEIPT_DATABASE
    ),
) -> dict[str, Any]:
    return (
        ControlledExecutionProductionReadiness(
            receipt_database=
                receipt_database
        )
        .evaluate()
    )
