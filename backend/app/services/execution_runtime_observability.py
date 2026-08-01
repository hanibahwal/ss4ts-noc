from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.execution_recovery_scheduler import (
    ExecutionRecoveryScheduler,
    RecoverySchedulerStatus,
)
from app.models.execution_runtime_observability import (
    RecoveryRuntimeObservability,
    RuntimeHealthStatus,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
)
from app.services.execution_recovery_scheduler_runtime import (
    ExecutionRecoverySchedulerRuntime,
    get_recovery_scheduler_runtime,
    runtime_enabled_from_environment,
)
from app.services.execution_recovery_scheduler_store import (
    DEFAULT_RECOVERY_SCHEDULER_ID,
    ExecutionRecoverySchedulerStore,
)
from app.services.execution_runtime_metrics_store import (
    DEFAULT_RUNTIME_METRICS_ID,
    ExecutionRuntimeMetricsStore,
    RuntimeMetricsVersionConflict,
)


class ExecutionRuntimeObservabilityService:
    """
    Build and persist recovery-runtime observability snapshots.

    This service reads runtime and scheduler coordination state only.
    It does not start or stop the runtime and does not execute managed
    device commands or perform network I/O.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTHORIZATION_DATABASE
        ),
        *,
        runtime: (
            ExecutionRecoverySchedulerRuntime
            | None
        ) = None,
        scheduler_store: (
            ExecutionRecoverySchedulerStore
            | None
        ) = None,
        metrics_store: (
            ExecutionRuntimeMetricsStore
            | None
        ) = None,
    ) -> None:
        self.database_path = Path(
            database_path
        )

        self.runtime = (
            runtime
            if runtime is not None
            else get_recovery_scheduler_runtime(
                self.database_path
            )
        )

        self.scheduler_store = (
            scheduler_store
            if scheduler_store is not None
            else ExecutionRecoverySchedulerStore(
                self.database_path
            )
        )

        self.metrics_store = (
            metrics_store
            if metrics_store is not None
            else ExecutionRuntimeMetricsStore(
                self.database_path
            )
        )

    @staticmethod
    def _health_status(
        *,
        runtime_environment_enabled: bool,
        runtime_running: bool,
        runtime_last_error: str | None,
        failed_cycle_count: int,
        successful_cycle_count: int,
        scheduler: (
            ExecutionRecoveryScheduler
            | None
        ),
    ) -> RuntimeHealthStatus:
        if not runtime_environment_enabled:
            return RuntimeHealthStatus.DISABLED

        if runtime_last_error:
            if runtime_running:
                return RuntimeHealthStatus.DEGRADED

            return RuntimeHealthStatus.UNHEALTHY

        if not runtime_running:
            return RuntimeHealthStatus.UNHEALTHY

        if scheduler is None:
            return RuntimeHealthStatus.DEGRADED

        if (
            scheduler.status
            == RecoverySchedulerStatus.FAILED
        ):
            return RuntimeHealthStatus.UNHEALTHY

        if failed_cycle_count > 0:
            if successful_cycle_count > 0:
                return RuntimeHealthStatus.DEGRADED

            return RuntimeHealthStatus.UNHEALTHY

        return RuntimeHealthStatus.HEALTHY

    def build_snapshot(
        self,
    ) -> RecoveryRuntimeObservability:
        runtime_state = self.runtime.state

        scheduler = self.scheduler_store.get(
            DEFAULT_RECOVERY_SCHEDULER_ID
        )

        runtime_environment_enabled = (
            runtime_enabled_from_environment()
        )

        last_result = runtime_state.last_result

        health_status = self._health_status(
            runtime_environment_enabled=
                runtime_environment_enabled,
            runtime_running=
                self.runtime.is_running,
            runtime_last_error=
                runtime_state.last_error,
            failed_cycle_count=
                runtime_state.failed_cycle_count,
            successful_cycle_count=
                runtime_state
                .successful_cycle_count,
            scheduler=scheduler,
        )

        scheduler_enabled = bool(
            scheduler.enabled
            if scheduler is not None
            else False
        )

        scheduler_due = bool(
            scheduler.is_due
            if scheduler is not None
            else False
        )

        metadata: dict[str, Any] = {
            "metrics_source":
                "runtime_live_state",
            "scheduler_id": (
                scheduler.scheduler_id
                if scheduler is not None
                else None
            ),
            "scheduler_status": (
                scheduler.status.value
                if scheduler is not None
                else None
            ),
            "scheduler_version": (
                scheduler.scheduler_version
                if scheduler is not None
                else None
            ),
            "runtime_environment_enabled":
                runtime_environment_enabled,
            "runtime_control_only":
                True,
            "execution_enabled":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        }

        return RecoveryRuntimeObservability(
            runtime_enabled=
                runtime_environment_enabled,
            runtime_running=
                self.runtime.is_running,
            scheduler_enabled=
                scheduler_enabled,
            scheduler_due=
                scheduler_due,
            health_status=
                health_status,
            cycle_count=
                runtime_state.cycle_count,
            successful_cycle_count=
                runtime_state
                .successful_cycle_count,
            failed_cycle_count=
                runtime_state.failed_cycle_count,
            last_recovered_count=(
                last_result.recovered
                if last_result is not None
                else 0
            ),
            last_skipped_count=(
                last_result.skipped
                if last_result is not None
                else 0
            ),
            last_failed_count=(
                last_result.failed
                if last_result is not None
                else 0
            ),
            started_at=
                runtime_state.started_at,
            stopped_at=
                runtime_state.stopped_at,
            last_cycle_started_at=
                runtime_state
                .last_cycle_started_at,
            last_cycle_completed_at=
                runtime_state
                .last_cycle_completed_at,
            last_error=
                runtime_state.last_error,
            metadata=metadata,
        )

    def persist_snapshot(
        self,
        metrics: RecoveryRuntimeObservability,
        *,
        metrics_id: str = (
            DEFAULT_RUNTIME_METRICS_ID
        ),
    ) -> tuple[
        RecoveryRuntimeObservability,
        int,
    ]:
        existing = self.metrics_store.get(
            metrics_id
        )

        if existing is None:
            return self.metrics_store.save(
                metrics,
                metrics_id=metrics_id,
            )

        _, version = existing

        try:
            return self.metrics_store.save(
                metrics,
                metrics_id=metrics_id,
                expected_version=version,
            )

        except RuntimeMetricsVersionConflict:
            current = self.metrics_store.get(
                metrics_id
            )

            if current is None:
                return self.metrics_store.save(
                    metrics,
                    metrics_id=metrics_id,
                )

            _, current_version = current

            return self.metrics_store.save(
                metrics,
                metrics_id=metrics_id,
                expected_version=
                    current_version,
            )

    def collect_and_persist(
        self,
        *,
        metrics_id: str = (
            DEFAULT_RUNTIME_METRICS_ID
        ),
    ) -> tuple[
        RecoveryRuntimeObservability,
        int,
    ]:
        snapshot = self.build_snapshot()

        return self.persist_snapshot(
            snapshot,
            metrics_id=metrics_id,
        )

    def get_current_metrics(
        self,
        *,
        metrics_id: str = (
            DEFAULT_RUNTIME_METRICS_ID
        ),
    ) -> tuple[
        RecoveryRuntimeObservability,
        int,
    ] | None:
        return self.metrics_store.get(
            metrics_id
        )

    def history(
        self,
        *,
        metrics_id: str = (
            DEFAULT_RUNTIME_METRICS_ID
        ),
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self.metrics_store.history(
            metrics_id,
            limit=limit,
            offset=offset,
        )


def collect_runtime_observability(
    database_path: str | Path = (
        DEFAULT_AUTHORIZATION_DATABASE
    ),
) -> tuple[
    RecoveryRuntimeObservability,
    int,
]:
    return ExecutionRuntimeObservabilityService(
        database_path
    ).collect_and_persist()
