from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1 import (
    execution_recovery_runtime,
)
from app.api.v1.router import (
    api_router,
)
from app.services.execution_recovery_scheduler_runtime import (
    RECOVERY_RUNTIME_ENABLED_ENV,
    reset_recovery_scheduler_runtime,
)


def run(coroutine):
    return asyncio.run(
        coroutine
    )


@pytest.fixture
def runtime_environment(
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
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    reset_recovery_scheduler_runtime()

    yield {
        "database":
            database,
    }

    runtime = (
        execution_recovery_runtime
        .get_runtime()
    )

    if runtime.is_running:
        run(
            runtime.stop()
        )

    reset_recovery_scheduler_runtime()


def test_get_runtime_snapshot(
    runtime_environment,
) -> None:
    result = run(
        execution_recovery_runtime
        .get_execution_recovery_runtime()
    )

    assert result["running"] is False
    assert result["is_running"] is False

    assert (
        result["environment_enabled"]
        is False
    )

    assert (
        result["safety"]
        ["execution_enabled"]
        is False
    )


def test_start_rejected_when_environment_disabled(
    runtime_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_recovery_runtime
            .start_execution_recovery_runtime()
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "runtime_environment_disabled"
    )


def test_start_runtime(
    runtime_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    async def scenario() -> None:
        result = await (
            execution_recovery_runtime
            .start_execution_recovery_runtime()
        )

        assert result["running"] is True
        assert result["is_running"] is True

        assert (
            result["environment_enabled"]
            is True
        )

        runtime = (
            execution_recovery_runtime
            .get_runtime()
        )

        await runtime.stop()

    run(
        scenario()
    )


def test_start_twice_returns_409(
    runtime_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    async def scenario() -> None:
        await (
            execution_recovery_runtime
            .start_execution_recovery_runtime()
        )

        with pytest.raises(
            HTTPException,
        ) as exc:
            await (
                execution_recovery_runtime
                .start_execution_recovery_runtime()
            )

        assert exc.value.status_code == 409

        assert (
            exc.value.detail["type"]
            == "runtime_already_running"
        )

        runtime = (
            execution_recovery_runtime
            .get_runtime()
        )

        await runtime.stop()

    run(
        scenario()
    )


def test_stop_runtime(
    runtime_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    async def scenario() -> None:
        await (
            execution_recovery_runtime
            .start_execution_recovery_runtime()
        )

        result = await (
            execution_recovery_runtime
            .stop_execution_recovery_runtime()
        )

        assert result["running"] is False
        assert result["is_running"] is False
        assert result["stopped_at"] is not None

    run(
        scenario()
    )


def test_stop_twice_returns_409(
    runtime_environment,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "true",
    )

    async def scenario() -> None:
        await (
            execution_recovery_runtime
            .start_execution_recovery_runtime()
        )

        await (
            execution_recovery_runtime
            .stop_execution_recovery_runtime()
        )

        with pytest.raises(
            HTTPException,
        ) as exc:
            await (
                execution_recovery_runtime
                .stop_execution_recovery_runtime()
            )

        assert exc.value.status_code == 409

        assert (
            exc.value.detail["type"]
            == "runtime_already_stopped"
        )

    run(
        scenario()
    )


def test_stop_before_start_returns_409(
    runtime_environment,
) -> None:
    with pytest.raises(
        HTTPException,
    ) as exc:
        run(
            execution_recovery_runtime
            .stop_execution_recovery_runtime()
        )

    assert exc.value.status_code == 409

    assert (
        exc.value.detail["type"]
        == "runtime_already_stopped"
    )


def test_snapshot_contains_safety_metadata(
    runtime_environment,
) -> None:
    result = run(
        execution_recovery_runtime
        .get_execution_recovery_runtime()
    )

    safety = result["safety"]

    assert (
        safety["runtime_environment_required"]
        is True
    )

    assert (
        safety["runtime_control_only"]
        is True
    )

    assert (
        safety["network_io_performed"]
        is False
    )

    assert (
        safety["device_command_executed"]
        is False
    )


def test_routes_are_registered() -> None:
    paths = {
        route.path
        for route in api_router.routes
    }

    expected = {
        (
            "/api/v1/"
            "execution-recovery-runtime"
        ),
        (
            "/api/v1/"
            "execution-recovery-runtime/start"
        ),
        (
            "/api/v1/"
            "execution-recovery-runtime/stop"
        ),
    }

    assert expected.issubset(
        paths
    )
