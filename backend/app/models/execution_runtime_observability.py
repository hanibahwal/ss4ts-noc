from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from enum import StrEnum
from typing import Any


class RuntimeHealthStatus(StrEnum):
    DISABLED = "disabled"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


def _text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _optional_datetime(
    value: Any,
) -> datetime | None:
    if value is None:
        return None

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
            return None

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


@dataclass(slots=True)
class RecoveryRuntimeObservability:
    runtime_enabled: bool

    runtime_running: bool

    scheduler_enabled: bool

    scheduler_due: bool

    health_status: RuntimeHealthStatus

    cycle_count: int = 0

    successful_cycle_count: int = 0

    failed_cycle_count: int = 0

    last_recovered_count: int = 0

    last_skipped_count: int = 0

    last_failed_count: int = 0

    started_at: datetime | None = None

    stopped_at: datetime | None = None

    last_cycle_started_at: datetime | None = None

    last_cycle_completed_at: datetime | None = None

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
        self.runtime_enabled = bool(
            self.runtime_enabled
        )

        self.runtime_running = bool(
            self.runtime_running
        )

        self.scheduler_enabled = bool(
            self.scheduler_enabled
        )

        self.scheduler_due = bool(
            self.scheduler_due
        )

        try:
            self.health_status = (
                self.health_status
                if isinstance(
                    self.health_status,
                    RuntimeHealthStatus,
                )
                else RuntimeHealthStatus(
                    _text(
                        self.health_status
                    ).lower()
                )
            )
        except ValueError:
            self.health_status = (
                RuntimeHealthStatus.UNKNOWN
            )

        self.cycle_count = int(
            self.cycle_count
        )

        self.successful_cycle_count = int(
            self.successful_cycle_count
        )

        self.failed_cycle_count = int(
            self.failed_cycle_count
        )

        self.last_recovered_count = int(
            self.last_recovered_count
        )

        self.last_skipped_count = int(
            self.last_skipped_count
        )

        self.last_failed_count = int(
            self.last_failed_count
        )

        self.started_at = (
            _optional_datetime(
                self.started_at
            )
        )

        self.stopped_at = (
            _optional_datetime(
                self.stopped_at
            )
        )

        self.last_cycle_started_at = (
            _optional_datetime(
                self.last_cycle_started_at
            )
        )

        self.last_cycle_completed_at = (
            _optional_datetime(
                self.last_cycle_completed_at
            )
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

        if (
            self.health_status
            == RuntimeHealthStatus.UNKNOWN
        ):
            raise ValueError(
                "Runtime health status "
                "must be known"
            )

        counters = {
            "cycle_count":
                self.cycle_count,
            "successful_cycle_count":
                self.successful_cycle_count,
            "failed_cycle_count":
                self.failed_cycle_count,
            "last_recovered_count":
                self.last_recovered_count,
            "last_skipped_count":
                self.last_skipped_count,
            "last_failed_count":
                self.last_failed_count,
        }

        for name, value in counters.items():
            if value < 0:
                raise ValueError(
                    f"{name} must not be negative"
                )

        if (
            self.successful_cycle_count
            + self.failed_cycle_count
            > self.cycle_count
        ):
            raise ValueError(
                "Successful and failed cycle "
                "counts cannot exceed cycle_count"
            )

        if (
            self.runtime_running
            and not self.runtime_enabled
        ):
            raise ValueError(
                "Running runtime must be enabled"
            )

        if (
            self.runtime_running
            and self.started_at is None
        ):
            raise ValueError(
                "Running runtime requires "
                "started_at"
            )

        if (
            self.stopped_at is not None
            and self.started_at is None
        ):
            raise ValueError(
                "stopped_at requires started_at"
            )

        if (
            self.started_at is not None
            and self.stopped_at is not None
            and self.stopped_at
            < self.started_at
        ):
            raise ValueError(
                "stopped_at cannot be before "
                "started_at"
            )

        if (
            self.last_cycle_completed_at
            is not None
            and self.last_cycle_started_at
            is None
        ):
            raise ValueError(
                "last_cycle_completed_at requires "
                "last_cycle_started_at"
            )

        if (
            self.last_cycle_started_at
            is not None
            and self.last_cycle_completed_at
            is not None
            and self.last_cycle_completed_at
            < self.last_cycle_started_at
        ):
            raise ValueError(
                "last_cycle_completed_at cannot "
                "be before last_cycle_started_at"
            )

    @property
    def last_cycle_duration_seconds(
        self,
    ) -> float | None:
        if (
            self.last_cycle_started_at is None
            or self.last_cycle_completed_at
            is None
        ):
            return None

        return round(
            max(
                0.0,
                (
                    self.last_cycle_completed_at
                    - self.last_cycle_started_at
                ).total_seconds(),
            ),
            6,
        )

    @property
    def last_processed_count(
        self,
    ) -> int:
        return (
            self.last_recovered_count
            + self.last_skipped_count
            + self.last_failed_count
        )

    @property
    def cycle_success_rate_percent(
        self,
    ) -> float:
        if self.cycle_count == 0:
            return 0.0

        return round(
            (
                self.successful_cycle_count
                / self.cycle_count
            )
            * 100.0,
            2,
        )

    @property
    def is_healthy(
        self,
    ) -> bool:
        return (
            self.health_status
            == RuntimeHealthStatus.HEALTHY
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "runtime_enabled":
                self.runtime_enabled,
            "runtime_running":
                self.runtime_running,
            "scheduler_enabled":
                self.scheduler_enabled,
            "scheduler_due":
                self.scheduler_due,
            "health_status":
                self.health_status.value,
            "is_healthy":
                self.is_healthy,
            "cycle_count":
                self.cycle_count,
            "successful_cycle_count":
                self.successful_cycle_count,
            "failed_cycle_count":
                self.failed_cycle_count,
            "cycle_success_rate_percent":
                self.cycle_success_rate_percent,
            "last_recovered_count":
                self.last_recovered_count,
            "last_skipped_count":
                self.last_skipped_count,
            "last_failed_count":
                self.last_failed_count,
            "last_processed_count":
                self.last_processed_count,
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
            "last_cycle_duration_seconds":
                self.last_cycle_duration_seconds,
            "last_error":
                self.last_error,
            "metadata":
                dict(self.metadata),
        }
