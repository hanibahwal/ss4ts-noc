from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import sqlite3

import pytest

from app.models.execution_runtime_observability import (
    RecoveryRuntimeObservability,
    RuntimeHealthStatus,
)
from app.services.execution_runtime_metrics_store import (
    DEFAULT_RUNTIME_METRICS_ID,
    ExecutionRuntimeMetricsStore,
    RuntimeMetricsVersionConflict,
)


def make_store(
    tmp_path,
) -> ExecutionRuntimeMetricsStore:
    return ExecutionRuntimeMetricsStore(
        tmp_path
        / "execution-authorization.db"
    )


def make_metrics(
    **overrides,
) -> RecoveryRuntimeObservability:
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
            "network_io_performed":
                False,
            "device_command_executed":
                False,
        },
    }

    values.update(
        overrides
    )

    return RecoveryRuntimeObservability(
        **values
    )


def test_schema_is_created(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

    assert (
        "execution_runtime_metrics"
        in tables
    )

    assert (
        "execution_runtime_metrics_history"
        in tables
    )


def test_create_metrics_snapshot(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    saved, version = store.save(
        make_metrics()
    )

    assert version == 1

    assert (
        saved.health_status
        == RuntimeHealthStatus.DISABLED
    )

    assert saved.runtime_running is False


def test_get_metrics_snapshot(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.save(
        make_metrics()
    )

    loaded = store.get()

    assert loaded is not None

    metrics, version = loaded

    assert version == 1

    assert (
        metrics.metadata[
            "execution_enabled"
        ]
        is False
    )


def test_update_metrics_snapshot(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.save(
        make_metrics()
    )

    now = datetime.now(
        timezone.utc
    )

    updated, version = store.save(
        make_metrics(
            runtime_enabled=True,
            runtime_running=True,
            scheduler_enabled=True,
            scheduler_due=False,
            health_status=(
                RuntimeHealthStatus.HEALTHY
            ),
            started_at=now,
            cycle_count=2,
            successful_cycle_count=2,
            last_recovered_count=1,
        ),
        expected_version=1,
    )

    assert version == 2
    assert updated.runtime_running is True
    assert updated.cycle_count == 2
    assert updated.last_recovered_count == 1


def test_update_requires_expected_version(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.save(
        make_metrics()
    )

    with pytest.raises(
        ValueError,
        match="expected_version",
    ):
        store.save(
            make_metrics()
        )


def test_stale_version_rejected(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.save(
        make_metrics()
    )

    store.save(
        make_metrics(),
        expected_version=1,
    )

    with pytest.raises(
        RuntimeMetricsVersionConflict,
    ) as exc:
        store.save(
            make_metrics(),
            expected_version=1,
        )

    assert exc.value.actual_version == 2


def test_history_is_recorded(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.save(
        make_metrics()
    )

    store.save(
        make_metrics(
            cycle_count=1,
            successful_cycle_count=1,
        ),
        expected_version=1,
    )

    history = store.history()

    assert len(history) == 2

    assert (
        history[0]["metrics_version"]
        == 2
    )

    assert (
        history[1]["metrics_version"]
        == 1
    )


def test_history_contains_snapshot(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    store.save(
        make_metrics(
            cycle_count=4,
            successful_cycle_count=3,
            failed_cycle_count=1,
        )
    )

    history = store.history()

    snapshot = history[0][
        "snapshot"
    ]

    assert (
        snapshot["metrics_id"]
        == DEFAULT_RUNTIME_METRICS_ID
    )

    assert snapshot["metrics_version"] == 1
    assert snapshot["cycle_count"] == 4

    assert (
        snapshot[
            "cycle_success_rate_percent"
        ]
        == 75.0
    )


def test_missing_metrics_returns_none(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    assert store.get() is None


def test_invalid_metrics_type_rejected(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="RecoveryRuntimeObservability",
    ):
        store.save(
            {},
        )  # type: ignore[arg-type]


def test_safety_metadata_persists(
    tmp_path,
) -> None:
    store = make_store(
        tmp_path
    )

    saved, _ = store.save(
        make_metrics()
    )

    assert (
        saved.metadata[
            "execution_enabled"
        ]
        is False
    )

    assert (
        saved.metadata[
            "network_io_performed"
        ]
        is False
    )

    assert (
        saved.metadata[
            "device_command_executed"
        ]
        is False
    )
