from __future__ import annotations

from dataclasses import dataclass, field
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import StrEnum
from typing import Any


DEFAULT_RECOVERY_INTERVAL_SECONDS = 60
DEFAULT_RECOVERY_BATCH_SIZE = 100


class RecoverySchedulerStatus(StrEnum):
    DISABLED = "disabled"
    IDLE = "idle"
    RUNNING = "running"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RecoverySchedulerRunStatus(StrEnum):
    NEVER_RUN = "never_run"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RecoverySchedulerError(
    RuntimeError
):
    """
    Base class for recovery-scheduler failures.
    """


class RecoverySchedulerVersionConflict(
    RecoverySchedulerError
):
    def __init__(
        self,
        *,
        scheduler_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.scheduler_id = str(
            scheduler_id
        ).strip()

        self.expected_version = int(
            expected_version
        )

        self.actual_version = int(
            actual_version
        )

        super().__init__(
            "Recovery scheduler version conflict: "
            f"expected={self.expected_version}, "
            f"actual={self.actual_version}"
        )


def _text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _datetime(
    value: Any,
) -> datetime:
    if isinstance(
        value,
        datetime,
    ):
        parsed = value
    else:
        text = _text(
            value
        )

        if not text:
            raise ValueError(
                "Scheduler datetime is required"
            )

        parsed = datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _optional_datetime(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

    return _datetime(
        value
    )


@dataclass(slots=True)
class ExecutionRecoveryScheduler:
    scheduler_id: str

    status: RecoverySchedulerStatus

    enabled: bool

    interval_seconds: int = (
        DEFAULT_RECOVERY_INTERVAL_SECONDS
    )

    batch_size: int = (
        DEFAULT_RECOVERY_BATCH_SIZE
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    last_run_started_at: datetime | None = None

    last_run_completed_at: datetime | None = None

    next_run_at: datetime | None = None

    last_run_status: RecoverySchedulerRunStatus = (
        RecoverySchedulerRunStatus.NEVER_RUN
    )

    last_run_recovered: int = 0

    last_run_skipped: int = 0

    last_run_failed: int = 0

    total_runs: int = 0

    total_recovered: int = 0

    total_skipped: int = 0

    total_failed: int = 0

    scheduler_version: int = 1

    last_error: str | None = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict
    )

    def __post_init__(
        self,
    ) -> None:
        self.scheduler_id = _text(
            self.scheduler_id
        )

        try:
            self.status = (
                self.status
                if isinstance(
                    self.status,
                    RecoverySchedulerStatus,
                )
                else RecoverySchedulerStatus(
                    _text(
                        self.status
                    ).lower()
                )
            )
        except ValueError:
            self.status = (
                RecoverySchedulerStatus.UNKNOWN
            )

        try:
            self.last_run_status = (
                self.last_run_status
                if isinstance(
                    self.last_run_status,
                    RecoverySchedulerRunStatus,
                )
                else RecoverySchedulerRunStatus(
                    _text(
                        self.last_run_status
                    ).lower()
                )
            )
        except ValueError:
            self.last_run_status = (
                RecoverySchedulerRunStatus.UNKNOWN
            )

        self.enabled = bool(
            self.enabled
        )

        self.interval_seconds = int(
            self.interval_seconds
        )

        self.batch_size = int(
            self.batch_size
        )

        self.created_at = _datetime(
            self.created_at
        )

        self.updated_at = _datetime(
            self.updated_at
        )

        self.last_run_started_at = (
            _optional_datetime(
                self.last_run_started_at
            )
        )

        self.last_run_completed_at = (
            _optional_datetime(
                self.last_run_completed_at
            )
        )

        self.next_run_at = (
            _optional_datetime(
                self.next_run_at
            )
        )

        self.last_run_recovered = int(
            self.last_run_recovered
        )

        self.last_run_skipped = int(
            self.last_run_skipped
        )

        self.last_run_failed = int(
            self.last_run_failed
        )

        self.total_runs = int(
            self.total_runs
        )

        self.total_recovered = int(
            self.total_recovered
        )

        self.total_skipped = int(
            self.total_skipped
        )

        self.total_failed = int(
            self.total_failed
        )

        self.scheduler_version = int(
            self.scheduler_version
        )

        self.last_error = (
            _text(
                self.last_error
            )
            or None
        )

        self.metadata = (
            dict(self.metadata)
            if isinstance(
                self.metadata,
                dict,
            )
            else {}
        )

        if not self.scheduler_id:
            raise ValueError(
                "scheduler_id must not be empty"
            )

        if (
            self.status
            == RecoverySchedulerStatus.UNKNOWN
        ):
            raise ValueError(
                "Recovery scheduler status "
                "must be known"
            )

        if (
            self.last_run_status
            == RecoverySchedulerRunStatus.UNKNOWN
        ):
            raise ValueError(
                "Recovery scheduler run status "
                "must be known"
            )

        if self.interval_seconds < 5:
            raise ValueError(
                "interval_seconds must be "
                "at least 5"
            )

        if self.interval_seconds > 86400:
            raise ValueError(
                "interval_seconds must not "
                "exceed 86400"
            )

        if self.batch_size < 1:
            raise ValueError(
                "batch_size must be at least 1"
            )

        if self.batch_size > 1000:
            raise ValueError(
                "batch_size must not exceed 1000"
            )

        if self.scheduler_version < 1:
            raise ValueError(
                "scheduler_version must "
                "be at least 1"
            )

        counters = {
            "last_run_recovered":
                self.last_run_recovered,
            "last_run_skipped":
                self.last_run_skipped,
            "last_run_failed":
                self.last_run_failed,
            "total_runs":
                self.total_runs,
            "total_recovered":
                self.total_recovered,
            "total_skipped":
                self.total_skipped,
            "total_failed":
                self.total_failed,
        }

        for name, value in counters.items():
            if value < 0:
                raise ValueError(
                    f"{name} must not be negative"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot be before "
                "created_at"
            )

        if (
            self.last_run_started_at is not None
            and self.last_run_started_at
            < self.created_at
        ):
            raise ValueError(
                "last_run_started_at cannot be "
                "before created_at"
            )

        if (
            self.last_run_completed_at is not None
            and self.last_run_started_at is None
        ):
            raise ValueError(
                "last_run_completed_at requires "
                "last_run_started_at"
            )

        if (
            self.last_run_started_at is not None
            and self.last_run_completed_at
            is not None
            and self.last_run_completed_at
            < self.last_run_started_at
        ):
            raise ValueError(
                "last_run_completed_at cannot be "
                "before last_run_started_at"
            )

        if (
            self.status
            == RecoverySchedulerStatus.RUNNING
            and self.last_run_started_at is None
        ):
            raise ValueError(
                "Running scheduler requires "
                "last_run_started_at"
            )

        if (
            self.last_run_status
            == RecoverySchedulerRunStatus.FAILED
            and not self.last_error
        ):
            raise ValueError(
                "Failed scheduler run requires "
                "last_error"
            )

        if (
            not self.enabled
            and self.status
            not in {
                RecoverySchedulerStatus.DISABLED,
                RecoverySchedulerStatus.FAILED,
            }
        ):
            raise ValueError(
                "Disabled scheduler must have "
                "disabled or failed status"
            )

        if (
            self.enabled
            and self.status
            == RecoverySchedulerStatus.DISABLED
        ):
            raise ValueError(
                "Enabled scheduler cannot have "
                "disabled status"
            )

    @property
    def last_run_processed(
        self,
    ) -> int:
        return (
            self.last_run_recovered
            + self.last_run_skipped
            + self.last_run_failed
        )

    @property
    def total_processed(
        self,
    ) -> int:
        return (
            self.total_recovered
            + self.total_skipped
            + self.total_failed
        )

    @property
    def has_run(
        self,
    ) -> bool:
        return self.total_runs > 0

    @property
    def is_running(
        self,
    ) -> bool:
        return (
            self.enabled
            and self.status
            == RecoverySchedulerStatus.RUNNING
        )

    @property
    def is_due(
        self,
    ) -> bool:
        if not self.enabled:
            return False

        if self.is_running:
            return False

        if self.next_run_at is None:
            return True

        return (
            datetime.now(
                timezone.utc
            )
            >= self.next_run_at
        )

    def is_due_at(
        self,
        *,
        now: datetime,
    ) -> bool:
        current = _datetime(
            now
        )

        if not self.enabled:
            return False

        if self.is_running:
            return False

        if self.next_run_at is None:
            return True

        return current >= self.next_run_at

    def calculate_next_run(
        self,
        *,
        from_time: datetime | None = None,
    ) -> datetime:
        base = (
            _datetime(from_time)
            if from_time is not None
            else datetime.now(
                timezone.utc
            )
        )

        return (
            base
            + timedelta(
                seconds=self.interval_seconds
            )
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "scheduler_id":
                self.scheduler_id,
            "status":
                self.status.value,
            "enabled":
                self.enabled,
            "interval_seconds":
                self.interval_seconds,
            "batch_size":
                self.batch_size,
            "created_at":
                self.created_at.isoformat(),
            "updated_at":
                self.updated_at.isoformat(),
            "last_run_started_at": (
                self.last_run_started_at
                .isoformat()
                if self.last_run_started_at
                else None
            ),
            "last_run_completed_at": (
                self.last_run_completed_at
                .isoformat()
                if self.last_run_completed_at
                else None
            ),
            "next_run_at": (
                self.next_run_at.isoformat()
                if self.next_run_at
                else None
            ),
            "last_run_status":
                self.last_run_status.value,
            "last_run_recovered":
                self.last_run_recovered,
            "last_run_skipped":
                self.last_run_skipped,
            "last_run_failed":
                self.last_run_failed,
            "last_run_processed":
                self.last_run_processed,
            "total_runs":
                self.total_runs,
            "total_recovered":
                self.total_recovered,
            "total_skipped":
                self.total_skipped,
            "total_failed":
                self.total_failed,
            "total_processed":
                self.total_processed,
            "scheduler_version":
                self.scheduler_version,
            "last_error":
                self.last_error,
            "has_run":
                self.has_run,
            "is_running":
                self.is_running,
            "is_due":
                self.is_due,
            "metadata":
                dict(self.metadata),
        }
