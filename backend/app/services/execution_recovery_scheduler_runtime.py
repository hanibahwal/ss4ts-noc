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
from pathlib import Path
from typing import Any

from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
)
from app.services.execution_recovery_scheduler import (
    ExecutionRecoverySchedulerService,
    RecoverySchedulerExecutionResult,
)
from app.services.execution_recovery_scheduler_store import (
    DEFAULT_RECOVERY_SCHEDULER_ID,
)


RECOVERY_RUNTIME_ENABLED_ENV = (
    "SS4TS_RECOVERY_SCHEDULER_RUNTIME_ENABLED"
)

RECOVERY_RUNTIME_POLL_SECONDS_ENV = (
    "SS4TS_RECOVERY_SCHEDULER_RUNTIME_POLL_SECONDS"
)

DEFAULT_RECOVERY_RUNTIME_POLL_SECONDS = 5.0


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
        RECOVERY_RUNTIME_ENABLED_ENV,
        default=False,
    )


def runtime_poll_seconds_from_environment(
) -> float:
    raw_value = os.getenv(
        RECOVERY_RUNTIME_POLL_SECONDS_ENV
    )

    if raw_value is None:
        return (
            DEFAULT_RECOVERY_RUNTIME_POLL_SECONDS
        )

    try:
        value = float(
            raw_value
        )
    except ValueError:
        return (
            DEFAULT_RECOVERY_RUNTIME_POLL_SECONDS
        )

    return max(
        0.1,
        min(
            value,
            3600.0,
        ),
    )


@dataclass(slots=True)
class RecoverySchedulerRuntimeState:
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

    last_result: (
        RecoverySchedulerExecutionResult
        | None
    ) = None

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
            "last_result": (
                self.last_result.to_dict()
                if self.last_result
                else None
            ),
            "last_error":
                self.last_error,
            "metadata":
                dict(self.metadata),
        }


class ExecutionRecoverySchedulerRuntime:
    """
    Safe asynchronous background runtime.

    The runtime periodically calls the existing run_once() scheduler
    service. It never executes commands against managed devices.

    Runtime startup remains disabled unless explicitly enabled by the
    SS4TS_RECOVERY_SCHEDULER_RUNTIME_ENABLED environment variable.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTHORIZATION_DATABASE
        ),
        *,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        poll_seconds: float = (
            DEFAULT_RECOVERY_RUNTIME_POLL_SECONDS
        ),
        scheduler_service: (
            ExecutionRecoverySchedulerService
            | None
        ) = None,
    ) -> None:
        self.database_path = Path(
            database_path
        )

        self.scheduler_id = str(
            scheduler_id
        ).strip()

        if not self.scheduler_id:
            raise ValueError(
                "scheduler_id must not be empty"
            )

        self.poll_seconds = float(
            poll_seconds
        )

        if self.poll_seconds < 0.1:
            raise ValueError(
                "poll_seconds must be at least 0.1"
            )

        if self.poll_seconds > 3600:
            raise ValueError(
                "poll_seconds must not exceed 3600"
            )

        self.scheduler_service = (
            scheduler_service
            if scheduler_service is not None
            else ExecutionRecoverySchedulerService(
                self.database_path
            )
        )

        self.state = (
            RecoverySchedulerRuntimeState(
                enabled=False,
                running=False,
                metadata={
                    "background_loop":
                        True,
                    "environment_gated":
                        True,
                    "execution_enabled":
                        False,
                    "network_io_performed":
                        False,
                    "device_command_executed":
                        False,
                },
            )
        )

        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._lifecycle_lock = asyncio.Lock()

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

            self._stop_event = asyncio.Event()

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
                    "ss4ts-recovery-"
                    "scheduler-runtime"
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
                    1.0,
                    self.poll_seconds + 1.0,
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
    ) -> RecoverySchedulerExecutionResult:
        self.state.last_cycle_started_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:
            result = await asyncio.to_thread(
                self.scheduler_service.run_once,
                scheduler_id=
                    self.scheduler_id,
                force=False,
            )

            self.state.last_result = result
            self.state.last_error = None

            self.state.successful_cycle_count += 1

            return result

        except Exception as exc:
            self.state.failed_cycle_count += 1
            self.state.last_error = str(
                exc
            )

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
                    # Isolate cycle failures so one exception does
                    # not permanently stop the runtime.
                    pass

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.poll_seconds,
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
        return self.state.to_dict()


_runtime_instance: (
    ExecutionRecoverySchedulerRuntime
    | None
) = None


def get_recovery_scheduler_runtime(
    database_path: str | Path = (
        DEFAULT_AUTHORIZATION_DATABASE
    ),
) -> ExecutionRecoverySchedulerRuntime:
    global _runtime_instance

    if _runtime_instance is None:
        _runtime_instance = (
            ExecutionRecoverySchedulerRuntime(
                database_path,
                poll_seconds=(
                    runtime_poll_seconds_from_environment()
                ),
            )
        )

    return _runtime_instance


def reset_recovery_scheduler_runtime(
) -> None:
    """
    Test helper for clearing the process-local singleton.

    The caller must stop a running instance before resetting it.
    """

    global _runtime_instance

    if (
        _runtime_instance is not None
        and _runtime_instance.is_running
    ):
        raise RuntimeError(
            "Cannot reset running recovery "
            "scheduler runtime"
        )

    _runtime_instance = None
