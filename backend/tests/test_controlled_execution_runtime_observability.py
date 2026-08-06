from __future__ import annotations

import asyncio

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi.responses import (
    PlainTextResponse,
)

from app.api.v1 import (
    controlled_execution_runtime_observability as api,
)
from app.api.v1.router import (
    api_router,
)
from app.services.controlled_execution_recovery_runtime import (
    CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
    ControlledExecutionRecoveryRuntime,
)
from app.services.controlled_execution_runtime_observability import (
    ControlledExecutionRuntimeObservability,
    ControlledRuntimeHealthStatus,
)
from app.services.controlled_execution_runtime_prometheus import (
    PROMETHEUS_CONTENT_TYPE,
    render_controlled_runtime_prometheus,
)


class FakeRecovery:
    def reconcile(
        self,
        *,
        stale_after_seconds: int,
        limit: int,
    ) -> dict:
        return {
            "recovery": {
                "recovered_count": 2,
            }
        }


def run(
    coroutine,
):
    return asyncio.run(
        coroutine
    )


def make_runtime(
) -> ControlledExecutionRecoveryRuntime:
    return ControlledExecutionRecoveryRuntime(
        recovery=FakeRecovery(),
        interval_seconds=30,
        stale_after_seconds=300,
        limit=100,
    )


def mark_running(
    runtime: ControlledExecutionRecoveryRuntime,
) -> None:
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


def test_disabled_health(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    service = (
        ControlledExecutionRuntimeObservability(
            runtime=make_runtime()
        )
    )

    snapshot = service.build_snapshot()

    assert (
        snapshot["runtime"]["health_status"]
        == ControlledRuntimeHealthStatus
        .DISABLED.value
    )


def test_enabled_but_stopped_is_unhealthy(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    snapshot = (
        ControlledExecutionRuntimeObservability(
            runtime=make_runtime()
        )
        .build_snapshot()
    )

    assert (
        snapshot["runtime"]["health_status"]
        == ControlledRuntimeHealthStatus
        .UNHEALTHY.value
    )


def test_running_runtime_is_healthy(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    runtime = make_runtime()

    mark_running(
        runtime
    )

    snapshot = (
        ControlledExecutionRuntimeObservability(
            runtime=runtime
        )
        .build_snapshot()
    )

    assert snapshot["runtime"]["running"] is True

    assert (
        snapshot["runtime"]["health_status"]
        == ControlledRuntimeHealthStatus
        .HEALTHY.value
    )


def test_running_runtime_with_error_is_degraded(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    runtime = make_runtime()

    mark_running(
        runtime
    )

    runtime.state.last_error = (
        "temporary failure"
    )

    snapshot = (
        ControlledExecutionRuntimeObservability(
            runtime=runtime
        )
        .build_snapshot()
    )

    assert (
        snapshot["runtime"]["health_status"]
        == ControlledRuntimeHealthStatus
        .DEGRADED.value
    )


def test_metrics_and_cycle_duration(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    runtime = make_runtime()

    mark_running(
        runtime
    )

    now = datetime.now(
        timezone.utc
    )

    runtime.state.cycle_count = 4
    runtime.state.successful_cycle_count = 3
    runtime.state.failed_cycle_count = 1
    runtime.state.last_recovered_count = 2
    runtime.state.total_recovered_count = 8
    runtime.state.last_cycle_started_at = (
        now
        - timedelta(seconds=1.5)
    )
    runtime.state.last_cycle_completed_at = now

    snapshot = (
        ControlledExecutionRuntimeObservability(
            runtime=runtime
        )
        .build_snapshot()
    )

    assert (
        snapshot["metrics"][
            "cycle_success_rate_percent"
        ]
        == 75.0
    )

    assert (
        snapshot["runtime"][
            "last_cycle_duration_seconds"
        ]
        == 1.5
    )

    assert (
        snapshot["metrics"][
            "total_recovered_count"
        ]
        == 8
    )


def test_prometheus_contains_core_metrics(
) -> None:
    runtime = make_runtime()

    snapshot = (
        ControlledExecutionRuntimeObservability(
            runtime=runtime
        )
        .build_snapshot()
    )

    content = (
        render_controlled_runtime_prometheus(
            snapshot
        )
    )

    assert (
        "ss4ts_controlled_recovery_cycles_total 0"
        in content
    )

    assert (
        "ss4ts_controlled_recovery_recovered_total 0"
        in content
    )

    assert (
        'ss4ts_controlled_recovery_health_status'
        '{status="disabled"} 1'
        in content
    )


def test_prometheus_renderer_rejects_invalid_input(
) -> None:
    import pytest

    with pytest.raises(
        TypeError,
        match="dictionary",
    ):
        render_controlled_runtime_prometheus(
            None
        )


def test_api_live_snapshot(
    monkeypatch,
) -> None:
    runtime = make_runtime()

    service = (
        ControlledExecutionRuntimeObservability(
            runtime=runtime
        )
    )

    monkeypatch.setattr(
        api,
        "get_controlled_runtime_observability_service",
        lambda: service,
    )

    result = run(
        api.get_controlled_runtime_observability()
    )

    assert "runtime" in result
    assert "metrics" in result

    assert (
        result["safety"][
            "observability_only"
        ]
        is True
    )


def test_api_prometheus(
    monkeypatch,
) -> None:
    service = (
        ControlledExecutionRuntimeObservability(
            runtime=make_runtime()
        )
    )

    monkeypatch.setattr(
        api,
        "get_controlled_runtime_observability_service",
        lambda: service,
    )

    response = run(
        api.get_controlled_runtime_prometheus()
    )

    assert isinstance(
        response,
        PlainTextResponse,
    )

    assert (
        PROMETHEUS_CONTENT_TYPE.split(
            ";"
        )[0].encode()
        in response.headers[
            "content-type"
        ].encode()
    )

    assert (
        b"ss4ts_controlled_recovery_runtime_enabled"
        in response.body
    )


def test_routes_are_registered(
) -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/remediation/"
            "controlled-recovery-runtime/"
            "observability"
        ),
        (
            "/api/v1/remediation/"
            "controlled-recovery-runtime/"
            "observability/health"
        ),
        (
            "/api/v1/remediation/"
            "controlled-recovery-runtime/"
            "observability/prometheus"
        ),
    }

    assert expected.issubset(
        paths
    )
