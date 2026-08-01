from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models.execution_runtime_observability import (
    RecoveryRuntimeObservability,
    RuntimeHealthStatus,
)


def make_metrics(
    **overrides,
) -> RecoveryRuntimeObservability:
    now = datetime.now(
        timezone.utc
    )

    values = {
        "runtime_enabled":
            False,
        "runtime_running":
            False,
        "scheduler_enabled":
            False,
        "scheduler_due":
            False,
        "health_status":
            RuntimeHealthStatus.DISABLED,
        "cycle_count":
            0,
        "successful_cycle_count":
            0,
        "failed_cycle_count":
            0,
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


def test_disabled_metrics() -> None:
    metrics = make_metrics()

    assert metrics.runtime_enabled is False
    assert metrics.runtime_running is False
    assert metrics.is_healthy is False

    assert (
        metrics.health_status
        == RuntimeHealthStatus.DISABLED
    )


def test_healthy_running_metrics() -> None:
    now = datetime.now(
        timezone.utc
    )

    metrics = make_metrics(
        runtime_enabled=True,
        runtime_running=True,
        scheduler_enabled=True,
        scheduler_due=False,
        health_status=(
            RuntimeHealthStatus.HEALTHY
        ),
        started_at=now,
        cycle_count=5,
        successful_cycle_count=5,
    )

    assert metrics.is_healthy is True

    assert (
        metrics.cycle_success_rate_percent
        == 100.0
    )


def test_cycle_duration() -> None:
    now = datetime.now(
        timezone.utc
    )

    metrics = make_metrics(
        last_cycle_started_at=now,
        last_cycle_completed_at=(
            now
            + timedelta(seconds=1.5)
        ),
    )

    assert (
        metrics.last_cycle_duration_seconds
        == 1.5
    )


def test_processed_count() -> None:
    metrics = make_metrics(
        last_recovered_count=2,
        last_skipped_count=1,
        last_failed_count=1,
    )

    assert metrics.last_processed_count == 4


def test_success_rate() -> None:
    metrics = make_metrics(
        cycle_count=4,
        successful_cycle_count=3,
        failed_cycle_count=1,
    )

    assert (
        metrics.cycle_success_rate_percent
        == 75.0
    )


def test_running_requires_enabled() -> None:
    with pytest.raises(
        ValueError,
        match="enabled",
    ):
        make_metrics(
            runtime_enabled=False,
            runtime_running=True,
            started_at=datetime.now(
                timezone.utc
            ),
        )


def test_running_requires_started_at() -> None:
    with pytest.raises(
        ValueError,
        match="started_at",
    ):
        make_metrics(
            runtime_enabled=True,
            runtime_running=True,
            started_at=None,
        )


def test_negative_counter_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="cycle_count",
    ):
        make_metrics(
            cycle_count=-1
        )


def test_cycle_result_counts_cannot_exceed_total() -> None:
    with pytest.raises(
        ValueError,
        match="cannot exceed",
    ):
        make_metrics(
            cycle_count=1,
            successful_cycle_count=1,
            failed_cycle_count=1,
        )


def test_completion_requires_start() -> None:
    with pytest.raises(
        ValueError,
        match="requires",
    ):
        make_metrics(
            last_cycle_completed_at=
                datetime.now(
                    timezone.utc
                ),
        )


def test_serialization() -> None:
    metrics = make_metrics(
        cycle_count=2,
        successful_cycle_count=1,
        failed_cycle_count=1,
        last_recovered_count=3,
    )

    payload = metrics.to_dict()

    assert payload["health_status"] == "disabled"
    assert payload["cycle_count"] == 2

    assert (
        payload["cycle_success_rate_percent"]
        == 50.0
    )

    assert payload["last_processed_count"] == 3

    assert (
        payload["metadata"]
        ["execution_enabled"]
        is False
    )
