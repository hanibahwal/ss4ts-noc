from __future__ import annotations

import asyncio

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.services.execution_recovery_scheduler import (
    RecoverySchedulerExecutionResult,
)
from app.services.execution_recovery_scheduler_runtime import (
    ExecutionRecoverySchedulerRuntime,
    RECOVERY_RUNTIME_ENABLED_ENV,
    RecoverySchedulerRuntimeState,
    environment_flag,
    reset_recovery_scheduler_runtime,
    runtime_enabled_from_environment,
)


@dataclass
class FakeSchedulerService:
    call_count: int = 0

    fail: bool = False

    def run_once(
        self,
        *,
        scheduler_id: str,
        force: bool,
    ) -> RecoverySchedulerExecutionResult:
        self.call_count += 1

        if self.fail:
            raise RuntimeError(
                "Simulated runtime failure"
            )

        return RecoverySchedulerExecutionResult(
            scheduler_id=scheduler_id,
            executed=False,
            reason="scheduler_disabled",
            metadata={
                "execution_enabled":
                    False,
            },
        )


def run(coroutine):
    return asyncio.run(
        coroutine
    )


def make_runtime(
    tmp_path: Path,
    *,
    service: FakeSchedulerService
        | None = None,
    poll_seconds: float = 0.1,
) -> ExecutionRecoverySchedulerRuntime:
    return ExecutionRecoverySchedulerRuntime(
        tmp_path
        / "execution-authorization.db",
        poll_seconds=poll_seconds,
        scheduler_service=(
            service
            if service is not None
            else FakeSchedulerService()
        ),
    )


def test_environment_flag_defaults_false(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        raising=False,
    )

    assert (
        runtime_enabled_from_environment()
        is False
    )


@pytest.mark.parametrize(
    "value",
    [
        "1",
        "true",
        "TRUE",
        "yes",
        "on",
        "enabled",
    ],
)
def test_environment_flag_accepts_true_values(
    monkeypatch,
    value,
) -> None:
    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        value,
    )

    assert (
        runtime_enabled_from_environment()
        is True
    )


def test_environment_flag_rejects_other_values(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        RECOVERY_RUNTIME_ENABLED_ENV,
        "disabled",
    )

    assert (
        environment_flag(
            RECOVERY_RUNTIME_ENABLED_ENV
        )
        is False
    )


def test_runtime_starts_and_stops(
    tmp_path,
) -> None:
    async def scenario():
        service = FakeSchedulerService()

        runtime = make_runtime(
            tmp_path,
            service=service,
        )

        started = await runtime.start()

        assert started is True
        assert runtime.is_running is True

        await asyncio.sleep(0.05)

        stopped = await runtime.stop()

        assert stopped is True
        assert runtime.is_running is False
        assert runtime.state.enabled is False
        assert runtime.state.stopped_at is not None
        assert service.call_count >= 1

    run(
        scenario()
    )


def test_second_start_is_ignored(
    tmp_path,
) -> None:
    async def scenario():
        runtime = make_runtime(
            tmp_path
        )

        first = await runtime.start()
        second = await runtime.start()

        assert first is True
        assert second is False

        await runtime.stop()

    run(
        scenario()
    )


def test_stop_without_start_returns_false(
    tmp_path,
) -> None:
    runtime = make_runtime(
        tmp_path
    )

    assert run(
        runtime.stop()
    ) is False


def test_run_cycle_records_result(
    tmp_path,
) -> None:
    async def scenario():
        service = FakeSchedulerService()

        runtime = make_runtime(
            tmp_path,
            service=service,
        )

        result = await runtime.run_cycle()

        assert (
            result.reason
            == "scheduler_disabled"
        )

        assert runtime.state.cycle_count == 1

        assert (
            runtime.state
            .successful_cycle_count
            == 1
        )

        assert runtime.state.failed_cycle_count == 0

        assert runtime.state.last_result is result

    run(
        scenario()
    )


def test_cycle_failure_is_recorded(
    tmp_path,
) -> None:
    async def scenario():
        service = FakeSchedulerService(
            fail=True
        )

        runtime = make_runtime(
            tmp_path,
            service=service,
        )

        with pytest.raises(
            RuntimeError,
            match="Simulated",
        ):
            await runtime.run_cycle()

        assert runtime.state.cycle_count == 1

        assert (
            runtime.state.failed_cycle_count
            == 1
        )

        assert (
            runtime.state.last_error
            == "Simulated runtime failure"
        )

    run(
        scenario()
    )


def test_loop_isolates_cycle_failures(
    tmp_path,
) -> None:
    async def scenario():
        service = FakeSchedulerService(
            fail=True
        )

        runtime = make_runtime(
            tmp_path,
            service=service,
            poll_seconds=0.1,
        )

        await runtime.start()

        await asyncio.sleep(0.25)

        assert runtime.is_running is True
        assert service.call_count >= 2

        await runtime.stop()

        assert (
            runtime.state.failed_cycle_count
            >= 2
        )

    run(
        scenario()
    )


def test_runtime_snapshot_is_safe(
    tmp_path,
) -> None:
    runtime = make_runtime(
        tmp_path
    )

    snapshot = runtime.snapshot()

    assert snapshot["running"] is False

    assert (
        snapshot["metadata"]
        ["execution_enabled"]
        is False
    )

    assert (
        snapshot["metadata"]
        ["network_io_performed"]
        is False
    )

    assert (
        snapshot["metadata"]
        ["device_command_executed"]
        is False
    )


def test_runtime_state_serialization() -> None:
    payload = (
        RecoverySchedulerRuntimeState(
            enabled=False,
            running=False,
            metadata={
                "execution_enabled":
                    False,
            },
        ).to_dict()
    )

    assert payload["enabled"] is False
    assert payload["running"] is False

    assert (
        payload["metadata"]
        ["execution_enabled"]
        is False
    )


def test_invalid_poll_seconds_rejected(
    tmp_path,
) -> None:
    with pytest.raises(
        ValueError,
        match="poll_seconds",
    ):
        ExecutionRecoverySchedulerRuntime(
            tmp_path / "runtime.db",
            poll_seconds=0,
            scheduler_service=
                FakeSchedulerService(),
        )


@pytest.fixture(autouse=True)
def reset_runtime_singleton():
    reset_recovery_scheduler_runtime()

    yield

    reset_recovery_scheduler_runtime()
