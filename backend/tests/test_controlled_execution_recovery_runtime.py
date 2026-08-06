from __future__ import annotations

import asyncio

import pytest

from app.services.controlled_execution_recovery_runtime import (
    ControlledExecutionRecoveryRuntime,
    get_controlled_recovery_runtime,
    reset_controlled_recovery_runtime,
    runtime_enabled_from_environment,
    runtime_interval_from_environment,
    runtime_limit_from_environment,
    runtime_stale_after_from_environment,
)


class FakeRecovery:
    def __init__(
        self,
        *,
        recovered_count: int = 0,
        fail: bool = False,
    ) -> None:
        self.recovered_count = (
            recovered_count
        )

        self.fail = fail
        self.calls = 0

    def reconcile(
        self,
        *,
        stale_after_seconds: int,
        limit: int,
    ) -> dict:
        self.calls += 1

        if self.fail:
            raise RuntimeError(
                "recovery failure"
            )

        return {
            "recovery": {
                "status": "COMPLETED",
                "stale_after_seconds":
                    stale_after_seconds,
                "limit":
                    limit,
                "recovered_count":
                    self.recovered_count,
                "events": [],
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            }
        }


@pytest.mark.asyncio
async def test_runtime_run_cycle_updates_state(
) -> None:
    recovery = FakeRecovery(
        recovered_count=3
    )

    runtime = (
        ControlledExecutionRecoveryRuntime(
            recovery=recovery,
            interval_seconds=1,
            stale_after_seconds=300,
            limit=100,
        )
    )

    result = await runtime.run_cycle()

    assert (
        result["recovery"][
            "recovered_count"
        ]
        == 3
    )

    snapshot = runtime.snapshot()

    assert snapshot["cycle_count"] == 1

    assert (
        snapshot[
            "successful_cycle_count"
        ]
        == 1
    )

    assert (
        snapshot[
            "total_recovered_count"
        ]
        == 3
    )

    assert (
        snapshot[
            "last_recovered_count"
        ]
        == 3
    )

    assert (
        snapshot["last_error"]
        is None
    )


@pytest.mark.asyncio
async def test_runtime_failed_cycle_is_recorded(
) -> None:
    runtime = (
        ControlledExecutionRecoveryRuntime(
            recovery=FakeRecovery(
                fail=True
            ),
            interval_seconds=1,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="recovery failure",
    ):
        await runtime.run_cycle()

    snapshot = runtime.snapshot()

    assert snapshot["cycle_count"] == 1

    assert (
        snapshot["failed_cycle_count"]
        == 1
    )

    assert (
        snapshot["last_error"]
        == "recovery failure"
    )


@pytest.mark.asyncio
async def test_runtime_start_stop_lifecycle(
) -> None:
    runtime = (
        ControlledExecutionRecoveryRuntime(
            recovery=FakeRecovery(),
            interval_seconds=1,
        )
    )

    started = await runtime.start()

    assert started is True
    assert runtime.is_running is True

    duplicate_start = (
        await runtime.start()
    )

    assert duplicate_start is False

    await asyncio.sleep(
        0.05
    )

    stopped = await runtime.stop()

    assert stopped is True
    assert runtime.is_running is False
    assert runtime.state.running is False


@pytest.mark.asyncio
async def test_runtime_cycle_lock_prevents_overlap(
) -> None:
    class SlowRecovery:
        def __init__(
            self,
        ) -> None:
            self.active = 0
            self.max_active = 0

        def reconcile(
            self,
            *,
            stale_after_seconds: int,
            limit: int,
        ) -> dict:
            import time

            self.active += 1

            self.max_active = max(
                self.max_active,
                self.active,
            )

            time.sleep(
                0.05
            )

            self.active -= 1

            return {
                "recovery": {
                    "recovered_count": 0,
                }
            }

    recovery = SlowRecovery()

    runtime = (
        ControlledExecutionRecoveryRuntime(
            recovery=recovery,
            interval_seconds=1,
        )
    )

    await asyncio.gather(
        runtime.run_cycle(),
        runtime.run_cycle(),
    )

    assert recovery.max_active == 1
    assert runtime.state.cycle_count == 2


def test_runtime_is_disabled_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED",
        raising=False,
    )

    assert (
        runtime_enabled_from_environment()
        is False
    )


def test_runtime_environment_settings(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_INTERVAL_SECONDS",
        "30",
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_RECOVERY_STALE_AFTER_SECONDS",
        "600",
    )

    monkeypatch.setenv(
        "SS4TS_CONTROLLED_RECOVERY_RUNTIME_LIMIT",
        "200",
    )

    assert (
        runtime_interval_from_environment()
        == 30
    )

    assert (
        runtime_stale_after_from_environment()
        == 600
    )

    assert (
        runtime_limit_from_environment()
        == 200
    )


def test_runtime_singleton(
) -> None:
    reset_controlled_recovery_runtime()

    first = (
        get_controlled_recovery_runtime()
    )

    second = (
        get_controlled_recovery_runtime()
    )

    assert first is second

    reset_controlled_recovery_runtime()
