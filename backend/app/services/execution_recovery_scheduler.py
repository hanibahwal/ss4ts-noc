from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from pathlib import Path
from typing import Any

from app.models.execution_recovery import (
    ExecutionRecovery,
    RecoveryStatus,
)
from app.models.execution_recovery_scheduler import (
    ExecutionRecoveryScheduler,
    RecoverySchedulerStatus,
    RecoverySchedulerVersionConflict,
)
from app.services.execution_authorization_store import (
    DEFAULT_AUTHORIZATION_DATABASE,
)
from app.services.execution_recovery import (
    ExecutionRecoveryService,
)
from app.services.execution_recovery_scheduler_store import (
    DEFAULT_RECOVERY_SCHEDULER_ID,
    ExecutionRecoverySchedulerStore,
)


@dataclass(slots=True)
class RecoverySchedulerExecutionResult:
    scheduler_id: str

    executed: bool

    reason: str

    recovered: int = 0

    skipped: int = 0

    failed: int = 0

    records: list[
        ExecutionRecovery
    ] = field(
        default_factory=list
    )

    scheduler: (
        ExecutionRecoveryScheduler
        | None
    ) = None

    error_message: str | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    @property
    def processed(
        self,
    ) -> int:
        return (
            self.recovered
            + self.skipped
            + self.failed
        )

    @property
    def succeeded(
        self,
    ) -> bool:
        return bool(
            self.executed
            and self.error_message is None
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "scheduler_id":
                self.scheduler_id,
            "executed":
                self.executed,
            "reason":
                self.reason,
            "recovered":
                self.recovered,
            "skipped":
                self.skipped,
            "failed":
                self.failed,
            "processed":
                self.processed,
            "succeeded":
                self.succeeded,
            "records": [
                record.to_dict()
                for record in self.records
            ],
            "scheduler": (
                self.scheduler.to_dict()
                if self.scheduler
                else None
            ),
            "error_message":
                self.error_message,
            "metadata":
                dict(self.metadata),
        }


class ExecutionRecoverySchedulerService:
    """
    Execute one safe recovery-scheduler cycle.

    The service does not create a background thread, timer, or process.
    A caller must invoke run_once() explicitly.

    No managed-device commands or network I/O are performed.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTHORIZATION_DATABASE
        ),
        *,
        scheduler_store: (
            ExecutionRecoverySchedulerStore
            | None
        ) = None,
        recovery_service: (
            ExecutionRecoveryService
            | None
        ) = None,
    ) -> None:
        self.database_path = Path(
            database_path
        )

        self.scheduler_store = (
            scheduler_store
            if scheduler_store is not None
            else ExecutionRecoverySchedulerStore(
                self.database_path
            )
        )

        self.recovery_service = (
            recovery_service
            if recovery_service is not None
            else ExecutionRecoveryService(
                self.database_path
            )
        )

    @staticmethod
    def _count_records(
        records: list[
            ExecutionRecovery
        ],
    ) -> tuple[int, int, int]:
        recovered = sum(
            1
            for record in records
            if (
                record.status
                == RecoveryStatus.RECOVERED
            )
        )

        skipped = sum(
            1
            for record in records
            if (
                record.status
                == RecoveryStatus.SKIPPED
            )
        )

        failed = sum(
            1
            for record in records
            if (
                record.status
                == RecoveryStatus.FAILED
            )
        )

        return (
            recovered,
            skipped,
            failed,
        )

    def ensure_default(
        self,
        *,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
    ) -> ExecutionRecoveryScheduler:
        return self.scheduler_store.create_default(
            scheduler_id=scheduler_id
        )

    def run_once(
        self,
        *,
        scheduler_id: str = (
            DEFAULT_RECOVERY_SCHEDULER_ID
        ),
        force: bool = False,
    ) -> RecoverySchedulerExecutionResult:
        scheduler = self.scheduler_store.get(
            scheduler_id
        )

        if scheduler is None:
            scheduler = (
                self.scheduler_store
                .create_default(
                    scheduler_id=scheduler_id
                )
            )

        safety = {
            "scheduler_loop_enabled":
                False,
            "execution_enabled":
                False,
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        }

        if not scheduler.enabled:
            return RecoverySchedulerExecutionResult(
                scheduler_id=
                    scheduler.scheduler_id,
                executed=False,
                reason="scheduler_disabled",
                scheduler=scheduler,
                metadata=safety,
            )

        if (
            scheduler.status
            == RecoverySchedulerStatus.RUNNING
        ):
            return RecoverySchedulerExecutionResult(
                scheduler_id=
                    scheduler.scheduler_id,
                executed=False,
                reason="scheduler_already_running",
                scheduler=scheduler,
                metadata=safety,
            )

        if (
            not force
            and not scheduler.is_due
        ):
            return RecoverySchedulerExecutionResult(
                scheduler_id=
                    scheduler.scheduler_id,
                executed=False,
                reason="scheduler_not_due",
                scheduler=scheduler,
                metadata=safety,
            )

        try:
            running = (
                self.scheduler_store
                .mark_run_started(
                    scheduler.scheduler_id,
                    expected_version=(
                        scheduler
                        .scheduler_version
                    ),
                )
            )

        except RecoverySchedulerVersionConflict:
            current = self.scheduler_store.get(
                scheduler.scheduler_id
            )

            return RecoverySchedulerExecutionResult(
                scheduler_id=
                    scheduler.scheduler_id,
                executed=False,
                reason="scheduler_version_conflict",
                scheduler=current,
                metadata=safety,
            )

        except ValueError as exc:
            current = self.scheduler_store.get(
                scheduler.scheduler_id
            )

            return RecoverySchedulerExecutionResult(
                scheduler_id=
                    scheduler.scheduler_id,
                executed=False,
                reason="scheduler_start_rejected",
                scheduler=current,
                error_message=str(exc),
                metadata=safety,
            )

        try:
            records = (
                self.recovery_service
                .recover_stale_workers(
                    limit=running.batch_size
                )
            )

            (
                recovered,
                skipped,
                failed,
            ) = self._count_records(
                records
            )

            completed = (
                self.scheduler_store
                .mark_run_completed(
                    running.scheduler_id,
                    expected_version=(
                        running
                        .scheduler_version
                    ),
                    recovered=recovered,
                    skipped=skipped,
                    failed=failed,
                )
            )

            return RecoverySchedulerExecutionResult(
                scheduler_id=
                    completed.scheduler_id,
                executed=True,
                reason="run_completed",
                recovered=recovered,
                skipped=skipped,
                failed=failed,
                records=records,
                scheduler=completed,
                metadata=safety,
            )

        except Exception as exc:
            current = self.scheduler_store.get(
                running.scheduler_id
            )

            failed_scheduler = current

            if (
                current is not None
                and current.status
                == RecoverySchedulerStatus.RUNNING
            ):
                try:
                    failed_scheduler = (
                        self.scheduler_store
                        .mark_run_failed(
                            current.scheduler_id,
                            expected_version=(
                                current
                                .scheduler_version
                            ),
                            error_message=str(exc),
                        )
                    )
                except Exception:
                    failed_scheduler = (
                        self.scheduler_store.get(
                            running.scheduler_id
                        )
                    )

            return RecoverySchedulerExecutionResult(
                scheduler_id=
                    running.scheduler_id,
                executed=True,
                reason="run_failed",
                failed=1,
                scheduler=failed_scheduler,
                error_message=str(exc),
                metadata=safety,
            )


def run_recovery_scheduler_once(
    database_path: str | Path = (
        DEFAULT_AUTHORIZATION_DATABASE
    ),
    *,
    scheduler_id: str = (
        DEFAULT_RECOVERY_SCHEDULER_ID
    ),
    force: bool = False,
) -> RecoverySchedulerExecutionResult:
    return ExecutionRecoverySchedulerService(
        database_path
    ).run_once(
        scheduler_id=scheduler_id,
        force=force,
    )
