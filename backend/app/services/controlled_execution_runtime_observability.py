from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from enum import Enum
from typing import Any

from app.services.controlled_execution_recovery_runtime import (
    ControlledExecutionRecoveryRuntime,
    get_controlled_recovery_runtime,
    runtime_enabled_from_environment,
)


class ControlledRuntimeHealthStatus(
    str,
    Enum,
):
    DISABLED = "disabled"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ControlledExecutionRuntimeObservability:
    """
    Build read-only observability snapshots for the controlled
    execution recovery runtime.

    This service does not start or stop the runtime, contact managed
    devices, perform network I/O, or execute device commands.
    """

    def __init__(
        self,
        *,
        runtime: (
            ControlledExecutionRecoveryRuntime
            | None
        ) = None,
    ) -> None:
        self.runtime = (
            runtime
            if runtime is not None
            else get_controlled_recovery_runtime()
        )

    @staticmethod
    def _health_status(
        *,
        environment_enabled: bool,
        runtime_running: bool,
        last_error: str | None,
        failed_cycle_count: int,
        successful_cycle_count: int,
    ) -> ControlledRuntimeHealthStatus:
        if not environment_enabled:
            return (
                ControlledRuntimeHealthStatus
                .DISABLED
            )

        if last_error:
            if runtime_running:
                return (
                    ControlledRuntimeHealthStatus
                    .DEGRADED
                )

            return (
                ControlledRuntimeHealthStatus
                .UNHEALTHY
            )

        if not runtime_running:
            return (
                ControlledRuntimeHealthStatus
                .UNHEALTHY
            )

        if failed_cycle_count > 0:
            if successful_cycle_count > 0:
                return (
                    ControlledRuntimeHealthStatus
                    .DEGRADED
                )

            return (
                ControlledRuntimeHealthStatus
                .UNHEALTHY
            )

        return (
            ControlledRuntimeHealthStatus
            .HEALTHY
        )

    @staticmethod
    def _duration_seconds(
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> float | None:
        if (
            started_at is None
            or completed_at is None
        ):
            return None

        duration = (
            completed_at
            - started_at
        ).total_seconds()

        return max(
            0.0,
            round(
                duration,
                6,
            ),
        )

    @staticmethod
    def _timestamp_age_seconds(
        timestamp: datetime | None,
    ) -> float | None:
        if timestamp is None:
            return None

        now = datetime.now(
            timezone.utc
        )

        age = (
            now
            - timestamp
        ).total_seconds()

        return max(
            0.0,
            round(
                age,
                6,
            ),
        )

    def build_snapshot(
        self,
    ) -> dict[str, Any]:
        state = self.runtime.state

        environment_enabled = (
            runtime_enabled_from_environment()
        )

        runtime_running = (
            self.runtime.is_running
        )

        health_status = self._health_status(
            environment_enabled=
                environment_enabled,
            runtime_running=
                runtime_running,
            last_error=
                state.last_error,
            failed_cycle_count=
                state.failed_cycle_count,
            successful_cycle_count=
                state.successful_cycle_count,
        )

        cycle_count = int(
            state.cycle_count
        )

        successful_cycle_count = int(
            state.successful_cycle_count
        )

        failed_cycle_count = int(
            state.failed_cycle_count
        )

        success_rate = (
            round(
                (
                    successful_cycle_count
                    / cycle_count
                )
                * 100.0,
                2,
            )
            if cycle_count > 0
            else 0.0
        )

        return {
            "service": {
                "name": (
                    "SS4TS Controlled Execution "
                    "Runtime Observability"
                ),
                "version":
                    "1.0.0-read-only",
            },
            "runtime": {
                "environment_enabled":
                    environment_enabled,
                "state_enabled":
                    bool(
                        state.enabled
                    ),
                "running":
                    runtime_running,
                "health_status":
                    health_status.value,
                "started_at": (
                    state.started_at.isoformat()
                    if state.started_at
                    else None
                ),
                "stopped_at": (
                    state.stopped_at.isoformat()
                    if state.stopped_at
                    else None
                ),
                "last_cycle_started_at": (
                    state
                    .last_cycle_started_at
                    .isoformat()
                    if (
                        state
                        .last_cycle_started_at
                    )
                    else None
                ),
                "last_cycle_completed_at": (
                    state
                    .last_cycle_completed_at
                    .isoformat()
                    if (
                        state
                        .last_cycle_completed_at
                    )
                    else None
                ),
                "last_cycle_duration_seconds":
                    self._duration_seconds(
                        state
                        .last_cycle_started_at,
                        state
                        .last_cycle_completed_at,
                    ),
                "last_cycle_age_seconds":
                    self._timestamp_age_seconds(
                        state
                        .last_cycle_completed_at
                    ),
                "last_error":
                    state.last_error,
            },
            "metrics": {
                "cycle_count":
                    cycle_count,
                "successful_cycle_count":
                    successful_cycle_count,
                "failed_cycle_count":
                    failed_cycle_count,
                "cycle_success_rate_percent":
                    success_rate,
                "last_recovered_count":
                    int(
                        state
                        .last_recovered_count
                    ),
                "total_recovered_count":
                    int(
                        state
                        .total_recovered_count
                    ),
            },
            "configuration": {
                "interval_seconds":
                    self.runtime
                    .interval_seconds,
                "stale_after_seconds":
                    self.runtime
                    .stale_after_seconds,
                "limit":
                    self.runtime.limit,
            },
            "safety": {
                "observability_only":
                    True,
                "fail_closed":
                    True,
                "simulation_only":
                    True,
                "execution_enabled":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
            "collected_at": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        }


_observability_instance: (
    ControlledExecutionRuntimeObservability
    | None
) = None


def get_controlled_runtime_observability(
) -> ControlledExecutionRuntimeObservability:
    global _observability_instance

    if _observability_instance is None:
        _observability_instance = (
            ControlledExecutionRuntimeObservability()
        )

    return _observability_instance


def reset_controlled_runtime_observability(
) -> None:
    global _observability_instance

    _observability_instance = None
