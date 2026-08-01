from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import (
    execution_runtime_observability,
)
from app.api.v1.router import (
    api_router,
)
from app.services.execution_recovery_scheduler_runtime import (
    reset_recovery_scheduler_runtime,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


@pytest.fixture
def observability_environment(
    tmp_path,
    monkeypatch,
):
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

    yield {
        "database":
            database,
    }

    reset_recovery_scheduler_runtime()


def test_live_snapshot(
    observability_environment,
) -> None:
    result = run(
        execution_runtime_observability
        .get_live_runtime_observability()
    )

    assert (
        result["health_status"]
        == "disabled"
    )

    assert result["persisted"] is False
    assert result["metrics_version"] is None

    assert (
        result["safety"]
        ["execution_enabled"]
        is False
    )


def test_current_before_collection_returns_404(
    observability_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_runtime_observability
            .get_current_runtime_observability()
        )

    assert exc.value.status_code == 404


def test_collect_metrics(
    observability_environment,
) -> None:
    result = run(
        execution_runtime_observability
        .collect_runtime_observability()
    )

    assert result["persisted"] is True
    assert result["metrics_version"] == 1

    assert (
        result["health_status"]
        == "disabled"
    )


def test_collect_updates_version(
    observability_environment,
) -> None:
    first = run(
        execution_runtime_observability
        .collect_runtime_observability()
    )

    second = run(
        execution_runtime_observability
        .collect_runtime_observability()
    )

    assert first["metrics_version"] == 1
    assert second["metrics_version"] == 2


def test_get_current_metrics(
    observability_environment,
) -> None:
    run(
        execution_runtime_observability
        .collect_runtime_observability()
    )

    result = run(
        execution_runtime_observability
        .get_current_runtime_observability()
    )

    assert result["persisted"] is True
    assert result["metrics_version"] == 1

    assert (
        result["metadata"]
        ["execution_enabled"]
        is False
    )


def test_history(
    observability_environment,
) -> None:
    run(
        execution_runtime_observability
        .collect_runtime_observability()
    )

    run(
        execution_runtime_observability
        .collect_runtime_observability()
    )

    result = run(
        execution_runtime_observability
        .runtime_observability_history(
            limit=100,
            offset=0,
        )
    )

    assert result["count"] == 2

    assert (
        result["records"][0]
        ["metrics_version"]
        == 2
    )

    assert (
        result["records"][1]
        ["metrics_version"]
        == 1
    )


def test_history_pagination(
    observability_environment,
) -> None:
    for _ in range(3):
        run(
            execution_runtime_observability
            .collect_runtime_observability()
        )

    result = run(
        execution_runtime_observability
        .runtime_observability_history(
            limit=1,
            offset=1,
        )
    )

    assert result["count"] == 1

    assert (
        result["records"][0]
        ["metrics_version"]
        == 2
    )


def test_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/"
            "execution-runtime-observability"
        ),
        (
            "/api/v1/"
            "execution-runtime-observability/"
            "collect"
        ),
        (
            "/api/v1/"
            "execution-runtime-observability/"
            "current"
        ),
        (
            "/api/v1/"
            "execution-runtime-observability/"
            "history"
        ),
    }

    assert expected.issubset(
        paths
    )
