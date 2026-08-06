from __future__ import annotations

import asyncio
import os

from dataclasses import (
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from typing import Any

from app.services.controlled_execution_recovery import (
    DEFAULT_RECOVERY_LIMIT,
    DEFAULT_STALE_AFTER_SECONDS,
    ControlledExecutionRecovery,
    recovery_service,
)


CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV = (
    "SS4TS_CONTROLLED_RECOVERY_RUNTIME_ENABLED"
)

CONTROLLED_RECOVERY_RUNTIME_INTERVAL_ENV = (
    "SS4TS_CONTROLLED_RECOVERY_RUNTIME_INTERVAL_SECONDS"
)

CONTROLLED_RECOVERY_RUNTIME_STALE_ENV = (
    "SS4TS_CONTROLLED_RECOVERY_STALE_AFTER_SECONDS"
)

CONTROLLED_RECOVERY_RUNTIME_LIMIT_ENV = (
    "SS4TS_CONTROLLED_RECOVERY_RUNTIME_LIMIT"
)


DEFAULT_CONTROLLED_RECOVERY_INTERVAL_SECONDS = 60.0


def environment_flag(
    name: str,
    *,
    default: bool = False,
) -> bool:
    value = os.getenv(
        name
    )

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }


def runtime_enabled_from_environment(
) -> bool:
    return environment_flag(
        CONTROLLED_RECOVERY_RUNTIME_ENABLED_ENV,
        default=False,
    )


def _float_from_environment(
    name: str,
    *,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    raw_value = os.getenv(
        name
    )

    if raw_value is None:
        return default

    try:
        value = float(
            raw_value
        )
    except ValueError:
        return default

    return max(
        minimum,
        min(
            value,
            maximum,
        ),
    )


def _int_from_environment(
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = os.getenv(
        name
    )

    if raw_value is None:
        return default

    try:
        value = int(
            raw_value
        )
    except ValueError:
        return default

    return max(
        minimum,
        min(
            value,
            maximum,
        ),
    )


def runtime_interval_from_environment(
) -> float:
    return _float_from_environment(
        CONTROLLED_RECOVERY_RUNTIME_INTERVAL_ENV,
        default=(
            DEFAULT_CONTROLLED_RECOVERY_INTERVAL_SECONDS
        ),
        minimum=1.0,
        maximum=3600.0,
    )


def runtime_stale_after_from_environment(
) -> int:
    return _int_from_environment(
        CONTROLLED_RECOVERY_RUNTIME_STALE_ENV,
        default=DEFAULT_STALE_AFTER_SECONDS,
        minimum=1,
        maximum=86400,
    )


def runtime_limit_from_environment(
) -> int:
    return _int_from_environment(
        CONTROLLED_RECOVERY_RUNTIME_LIMIT_ENV,
        default=DEFAULT_RECOVERY_LIMIT,
        minimum=1,
        maximum=500,
    )


@dataclass(slots=True)
class ControlledRecoveryRuntimeState:
    enabled: bool = False
    running: bool = False

    started_at: datetime | None = None
    stopped_at: datetime | None = None

    last_cycle_started_at: (
        datetime | None
    ) = None

    last_cycle_completed_at: (
        datetime | None
    ) = None

    cycle_count: int = 0
    successful_cycle_count: int = 0
    failed_cycle_count: int = 0

    total_recovered_count: int = 0
    last_recovered_count: int = 0

    last_result: dict[str, Any] | None = None
    last_error: str | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "enabled":
                self.enabled,
            "running":
                self.running,
            "started_at": (
                self.started_at.isoformat()
                if self.started_at
                else None
            ),
            "stopped_at": (
                self.stopped_at.isoformat()
                if self.stopped_at
                else None
            ),
            "last_cycle_started_at": (
                self.last_cycle_started_at
                .isoformat()
                if self.last_cycle_started_at
                else None
            ),
            "last_cycle_completed_at": (
                self.last_cycle_completed_at
                .isoformat()
                if self.last_cycle_completed_at
                else None
            ),
            "cycle_count":
                self.cycle_count,
            "successful_cycle_count":
                self.successful_cycle_count,
            "failed_cycle_count":
                self.failed_cycle_count,
            "total_recovered_count":
                self.total_recovered_count,
            "last_recovered_count":
                self.last_recovered_count,
            "last_result":
                self.last_result,
            "last_error":
                self.last_error,
            "metadata":
                dict(
                    self.metadata
                ),
        }


class ControlledExecutionRecoveryRuntime:
    """
    Periodic fail-closed recovery runtime.

    It only reconciles persisted approval and receipt states.
    It never contacts network devices and never executes commands.
    """

    def __init__(
        self,
        *,
        recovery: (
            ControlledExecutionRecovery
        ) = recovery_service,
        interval_seconds: float = (
            DEFAULT_CONTROLLED_RECOVERY_INTERVAL_SECONDS
        ),
        stale_after_seconds: int = (
            DEFAULT_STALE_AFTER_SECONDS
        ),
        limit: int = DEFAULT_RECOVERY_LIMIT,
    ) -> None:
        self.recovery = recovery

        self.interval_seconds = float(
            interval_seconds
        )

        if self.interval_seconds < 1:
            raise ValueError(
                "interval_seconds must be at least 1"
            )

        if self.interval_seconds > 3600:
            raise ValueError(
                "interval_seconds must not exceed 3600"
            )

        self.stale_after_seconds = int(
            stale_after_seconds
        )

        if self.stale_after_seconds < 1:
            raise ValueError(
                "stale_after_seconds must be positive"
            )

        if self.stale_after_seconds > 86400:
            raise ValueError(
                "stale_after_seconds must not exceed 86400"
            )

        self.limit = int(
            limit
        )

        if self.limit < 1:
            raise ValueError(
                "limit must be at least 1"
            )

        if self.limit > 500:
            raise ValueError(
                "limit must not exceed 500"
            )

        self.state = (
            ControlledRecoveryRuntimeState(
                metadata={
                    "background_loop":
                        True,
                    "environment_gated":
                        True,
                    "fail_closed":
                        True,
                    "simulation_only":
                        True,
                    "network_io_performed":
                        False,
                    "device_command_executed":
                        False,
                    "interval_seconds":
                        self.interval_seconds,
                    "stale_after_seconds":
                        self.stale_after_seconds,
                    "limit":
                        self.limit,
                }
            )
        )

        self._task: (
            asyncio.Task | None
        ) = None

        self._stop_event = (
            asyncio.Event()
        )

        self._lifecycle_lock = (
            asyncio.Lock()
        )

        self._cycle_lock = (
            asyncio.Lock()
        )

    @property
    def is_running(
        self,
    ) -> bool:
        return bool(
            self._task is not None
            and not self._task.done()
            and self.state.running
        )

    async def start(
        self,
    ) -> bool:
        async with self._lifecycle_lock:
            if self.is_running:
                return False

            self._stop_event = (
                asyncio.Event()
            )

            now = datetime.now(
                timezone.utc
            )

            self.state.enabled = True
            self.state.running = True
            self.state.started_at = now
            self.state.stopped_at = None
            self.state.last_error = None

            self._task = asyncio.create_task(
                self._run_loop(),
                name=(
                    "ss4ts-controlled-"
                    "execution-recovery-runtime"
                ),
            )

            return True

    async def stop(
        self,
    ) -> bool:
        async with self._lifecycle_lock:
            task = self._task

            if task is None:
                self.state.enabled = False
                self.state.running = False
                return False

            self._stop_event.set()

        try:
            await asyncio.wait_for(
                task,
                timeout=max(
                    2.0,
                    self.interval_seconds
                    + 1.0,
                ),
            )

        except asyncio.TimeoutError:
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        finally:
            async with self._lifecycle_lock:
                self._task = None
                self.state.enabled = False
                self.state.running = False
                self.state.stopped_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

        return True

    async def run_cycle(
        self,
    ) -> dict[str, Any]:
        async with self._cycle_lock:
            self.state.last_cycle_started_at = (
                datetime.now(
                    timezone.utc
                )
            )

            try:
                result = await asyncio.to_thread(
                    self.recovery.reconcile,
                    stale_after_seconds=(
                        self.stale_after_seconds
                    ),
                    limit=self.limit,
                )

                recovered_count = int(
                    result.get(
                        "recovery",
                        {},
                    ).get(
                        "recovered_count",
                        0,
                    )
                )

                self.state.last_result = result
                self.state.last_error = None
                self.state.last_recovered_count = (
                    recovered_count
                )

                self.state.total_recovered_count += (
                    recovered_count
                )

                self.state.successful_cycle_count += 1

                return result

            except Exception as exc:
                self.state.failed_cycle_count += 1
                self.state.last_error = str(
                    exc
                )
                self.state.last_recovered_count = 0

                raise

            finally:
                self.state.cycle_count += 1

                self.state.last_cycle_completed_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

    async def _run_loop(
        self,
    ) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    await self.run_cycle()

                except asyncio.CancelledError:
                    raise

                except Exception:
                    # A failed cycle must not permanently
                    # terminate recovery supervision.
                    pass

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=(
                            self.interval_seconds
                        ),
                    )

                except asyncio.TimeoutError:
                    continue

        except asyncio.CancelledError:
            raise

        finally:
            self.state.running = False

    def snapshot(
        self,
    ) -> dict[str, Any]:
        payload = self.state.to_dict()

        payload["is_running"] = (
            self.is_running
        )

        return payload


_runtime_instance: (
    ControlledExecutionRecoveryRuntime
    | None
) = None


def get_controlled_recovery_runtime(
) -> ControlledExecutionRecoveryRuntime:
    global _runtime_instance

    if _runtime_instance is None:
        _runtime_instance = (
            ControlledExecutionRecoveryRuntime(
                interval_seconds=(
                    runtime_interval_from_environment()
                ),
                stale_after_seconds=(
                    runtime_stale_after_from_environment()
                ),
                limit=(
                    runtime_limit_from_environment()
                ),
            )
        )

    return _runtime_instance


def reset_controlled_recovery_runtime(
) -> None:
    """
    Test helper for clearing the process-local singleton.
    """
    global _runtime_instance

    if (
        _runtime_instance is not None
        and _runtime_instance.is_running
    ):
        raise RuntimeError(
            "Cannot reset running controlled "
            "recovery runtime"
        )

    _runtime_instance = None
