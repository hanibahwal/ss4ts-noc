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
    execution_runtime_observability,
    execution_runtime_prometheus,
)
from app.api.v1.router import (
    api_router,
)
from app.models.execution_runtime_observability import (
    RecoveryRuntimeObservability,
    RuntimeHealthStatus,
)
from app.services.prometheus_runtime_metrics import (
    PROMETHEUS_CONTENT_TYPE,
    render_runtime_prometheus_metrics,
)
from app.services.execution_recovery_scheduler_runtime import (
    reset_recovery_scheduler_runtime,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


def make_metrics(
    **overrides,
) -> RecoveryRuntimeObservability:
    now = datetime.now(
        timezone.utc
    )

    values = {
        "runtime_enabled":
            True,
        "runtime_running":
            True,
        "scheduler_enabled":
            True,
        "scheduler_due":
            False,
        "health_status":
            RuntimeHealthStatus.HEALTHY,
        "cycle_count":
            4,
        "successful_cycle_count":
            3,
        "failed_cycle_count":
            1,
        "last_recovered_count":
            2,
        "last_skipped_count":
            1,
        "last_failed_count":
            1,
        "started_at":
            now - timedelta(minutes=5),
        "last_cycle_started_at":
            now - timedelta(seconds=2),
        "last_cycle_completed_at":
            now,
        "metadata": {
            "execution_enabled":
                False,
        },
    }

    values.update(
        overrides
    )

    return RecoveryRuntimeObservability(
        **values
    )


def test_renderer_contains_core_metrics() -> None:
    content = (
        render_runtime_prometheus_metrics(
            make_metrics(),
            metrics_version=7,
        )
    )

    assert (
        "ss4ts_runtime_enabled 1"
        in content
    )

    assert (
        "ss4ts_runtime_running 1"
        in content
    )

    assert (
        "ss4ts_scheduler_enabled 1"
        in content
    )

    assert (
        "ss4ts_runtime_cycle_count 4"
        in content
    )

    assert (
        "ss4ts_runtime_metrics_version 7"
        in content
    )


def test_health_is_exported_as_one_hot() -> None:
    content = (
        render_runtime_prometheus_metrics(
            make_metrics(
                health_status=(
                    RuntimeHealthStatus.DEGRADED
                )
            )
        )
    )

    assert (
        'ss4ts_runtime_health_status'
        '{status="degraded"} 1'
        in content
    )

    assert (
        'ss4ts_runtime_health_status'
        '{status="healthy"} 0'
        in content
    )


def test_last_cycle_duration_is_exported() -> None:
    content = (
        render_runtime_prometheus_metrics(
            make_metrics()
        )
    )

    assert (
        "ss4ts_runtime_last_cycle_duration_seconds 2.0"
        in content
    )


def test_last_error_metric() -> None:
    content = (
        render_runtime_prometheus_metrics(
            make_metrics(
                last_error="Test failure"
            )
        )
    )

    assert (
        "ss4ts_runtime_last_error 1"
        in content
    )


def test_renderer_rejects_invalid_type() -> None:
    try:
        render_runtime_prometheus_metrics(
            {},
        )  # type: ignore[arg-type]
    except TypeError as exc:
        assert (
            "RecoveryRuntimeObservability"
            in str(exc)
        )
    else:
        raise AssertionError(
            "TypeError was not raised"
        )


def test_content_has_prometheus_metadata() -> None:
    content = (
        render_runtime_prometheus_metrics(
            make_metrics()
        )
    )

    assert (
        "# HELP ss4ts_runtime_enabled"
        in content
    )

    assert (
        "# TYPE ss4ts_runtime_enabled gauge"
        in content
    )

    assert (
        "# TYPE ss4ts_runtime_cycle_count counter"
        in content
    )


def test_prometheus_endpoint(
    tmp_path,
    monkeypatch,
) -> None:
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    monkeypatch.setenv(
        "SS4TS_EXECUTION_AUTH_DB",
        str(database),
    )

    monkeypatch.delenv(
        "SS4TS_RECOVERY_SCHEDULER_RUNTIME_ENABLED",
        raising=False,
    )

    reset_recovery_scheduler_runtime()

    response = run(
        execution_runtime_prometheus
        .execution_runtime_prometheus_metrics()
    )

    assert isinstance(
        response,
        PlainTextResponse,
    )

    content = response.body.decode(
        "utf-8"
    )

    assert (
        "ss4ts_runtime_enabled 0"
        in content
    )

    assert (
        'ss4ts_runtime_health_status'
        '{status="disabled"} 1'
        in content
    )

    reset_recovery_scheduler_runtime()


def test_endpoint_uses_persisted_version(
    tmp_path,
    monkeypatch,
) -> None:
    database = (
        tmp_path
        / "execution-authorization.db"
    )

    monkeypatch.setenv(
        "SS4TS_EXECUTION_AUTH_DB",
        str(database),
    )

    monkeypatch.delenv(
        "SS4TS_RECOVERY_SCHEDULER_RUNTIME_ENABLED",
        raising=False,
    )

    reset_recovery_scheduler_runtime()

    run(
        execution_runtime_observability
        .collect_runtime_observability()
    )

    response = run(
        execution_runtime_prometheus
        .execution_runtime_prometheus_metrics()
    )

    content = response.body.decode(
        "utf-8"
    )

    assert (
        "ss4ts_runtime_metrics_version 1"
        in content
    )

    reset_recovery_scheduler_runtime()


def test_prometheus_content_type() -> None:
    assert (
        PROMETHEUS_CONTENT_TYPE
        == (
            "text/plain; version=0.0.4; "
            "charset=utf-8"
        )
    )


def test_route_is_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    assert (
        "/api/v1/"
        "execution-runtime-observability/"
        "prometheus"
        in paths
    )
