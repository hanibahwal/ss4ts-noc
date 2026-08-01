from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest

from app.models.execution_recovery_scheduler import (
    RecoverySchedulerStatus,
)
from app.models.execution_runtime_observability import (
    RuntimeHealthStatus,
)
from app.services.execution_recovery_scheduler import (
    RecoverySchedulerExecutionResult,
)
from app.services.execution_recovery_scheduler_runtime import (
    ExecutionRecoverySchedulerRuntime,
    RECOVERY_RUNTIME_ENABLED_ENV,
)
from app.services.execution_recovery_scheduler_store import (
    ExecutionRecoverySchedulerStore,
)
from app.services.execution_runtime_metrics_store import (
    ExecutionRuntimeMetricsStore,
)
from app.services.execution_runtime_observability import (
    ExecutionRuntimeObservabilityService,
)


class FakeSchedulerService:
    def run_once(
        self,
        *,
        scheduler_id: str,
        force: bool,
    ) -> RecoverySchedulerExecutionResult:
        return RecoverySchedulerExecutionResult(
            scheduler_id=scheduler_id,
            executed=False,
            reason="scheduler_disabled",
            recovered=0,
            skipped=0,
            failed=0,
            metadata={
                "execution_enabled":
                    False,
            },
        )


def make_service(
    tmp_path: Path,
):
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    scheduler_store = (
        ExecutionRecoverySchedulerStore(
            database
        )
    )

    scheduler_store.create_default()

    runtime = (
        ExecutionRecoverySchedulerRuntime(
            database,
            poll_seconds=1,
            scheduler_service=
                FakeSchedulerService(),
        )
    )

    metrics_store = (
        ExecutionRuntimeMetricsStore(
            database
        )
    )

    service = (
        ExecutionRuntimeObservabilityService(
            database,
            runtime=runtime,
            scheduler_store=
                scheduler_store,
            metrics_store=
                metrics_store,
        )
    )

    return {
        "database":
            database,
        "runtime":
            runtime,
        "scheduler_store":
            scheduler_store,
        "metrics_store":
            metrics_store,
        "service":
            service,
    }


def test_disabled_runtime_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    metrics = environment[
        "service"
    ].build_snapshot()

    assert metrics.runtime_enabled is False
    assert metrics.runtime_running is False

    assert (
        metrics.health_status
        == RuntimeHealthStatus.DISABLED
    )


def test_enabled_but_stopped_runtime_is_unhealthy(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    metrics = environment[
        "service"
    ].build_snapshot()

    assert metrics.runtime_enabled is True
    assert metrics.runtime_running is False

    assert (
        metrics.health_status
        == RuntimeHealthStatus.UNHEALTHY
    )


def test_running_runtime_is_healthy(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    runtime = environment[
        "runtime"
    ]

    runtime.state.enabled = True
    runtime.state.running = True
    runtime.state.started_at = (
        datetime.now(
            timezone.utc
        )
    )

    class FakeTask:
        def done(
            self,
        ) -> bool:
            return False

    runtime._task = FakeTask()

    metrics = environment[
        "service"
    ].build_snapshot()

    assert metrics.runtime_running is True

    assert (
        metrics.health_status
        == RuntimeHealthStatus.HEALTHY
    )


def test_runtime_error_is_degraded_when_running(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    runtime = environment[
        "runtime"
    ]

    runtime.state.enabled = True
    runtime.state.running = True
    runtime.state.started_at = (
        datetime.now(
            timezone.utc
        )
    )

    runtime.state.last_error = (
        "Temporary runtime failure"
    )

    class FakeTask:
        def done(
            self,
        ) -> bool:
            return False

    runtime._task = FakeTask()

    metrics = environment[
        "service"
    ].build_snapshot()

    assert (
        metrics.health_status
        == RuntimeHealthStatus.DEGRADED
    )

    assert (
        metrics.last_error
        == "Temporary runtime failure"
    )


def test_failed_scheduler_is_unhealthy(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    scheduler = environment[
        "scheduler_store"
    ].get()

    assert scheduler is not None

    enabled = environment[
        "scheduler_store"
    ].enable(
        expected_version=
            scheduler.scheduler_version
    )

    running = environment[
        "scheduler_store"
    ].mark_run_started(
        expected_version=
            enabled.scheduler_version
    )

    environment[
        "scheduler_store"
    ].mark_run_failed(
        expected_version=
            running.scheduler_version,
        error_message=
            "Scheduler failed",
    )

    runtime = environment[
        "runtime"
    ]

    runtime.state.enabled = True
    runtime.state.running = True
    runtime.state.started_at = (
        datetime.now(
            timezone.utc
        )
    )

    class FakeTask:
        def done(
            self,
        ) -> bool:
            return False

    runtime._task = FakeTask()

    metrics = environment[
        "service"
    ].build_snapshot()

    assert (
        metrics.metadata["scheduler_status"]
        == RecoverySchedulerStatus
        .FAILED.value
    )

    assert (
        metrics.health_status
        == RuntimeHealthStatus.UNHEALTHY
    )


def test_last_result_counts_are_collected(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    environment[
        "runtime"
    ].state.last_result = (
        RecoverySchedulerExecutionResult(
            scheduler_id=
                "recovery-scheduler:default",
            executed=True,
            reason="run_completed",
            recovered=3,
            skipped=2,
            failed=1,
        )
    )

    metrics = environment[
        "service"
    ].build_snapshot()

    assert metrics.last_recovered_count == 3
    assert metrics.last_skipped_count == 2
    assert metrics.last_failed_count == 1
    assert metrics.last_processed_count == 6


def test_collect_and_persist_creates_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    saved, version = environment[
        "service"
    ].collect_and_persist()

    assert version == 1

    assert (
        saved.health_status
        == RuntimeHealthStatus.DISABLED
    )

    assert (
        len(
            environment[
                "metrics_store"
            ].history()
        )
        == 1
    )


def test_collect_and_persist_updates_snapshot(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    environment[
        "service"
    ].collect_and_persist()

    environment[
        "runtime"
    ].state.cycle_count = 1

    environment[
        "runtime"
    ].state.successful_cycle_count = 1

    saved, version = environment[
        "service"
    ].collect_and_persist()

    assert version == 2
    assert saved.cycle_count == 1

    assert (
        saved.successful_cycle_count
        == 1
    )

    assert (
        len(
            environment[
                "metrics_store"
            ].history()
        )
        == 2
    )


def test_get_current_metrics(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    environment[
        "service"
    ].collect_and_persist()

    current = environment[
        "service"
    ].get_current_metrics()

    assert current is not None

    metrics, version = current

    assert version == 1

    assert (
        metrics.metadata[
            "execution_enabled"
        ]
        is False
    )


def test_history_delegates_to_store(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    environment[
        "service"
    ].collect_and_persist()

    history = environment[
        "service"
    ].history(
        limit=10,
        offset=0,
    )

    assert len(history) == 1

    assert (
        history[0]["metrics_version"]
        == 1
    )


def test_snapshot_safety_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    environment = make_service(
        tmp_path
    )

    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    metrics = environment[
        "service"
    ].build_snapshot()

    assert (
        metrics.metadata[
            "execution_enabled"
        ]
        is False
    )

    assert (
        metrics.metadata[
            "network_io_performed"
        ]
        is False
    )

    assert (
        metrics.metadata[
            "device_command_executed"
        ]
        is False
    )
