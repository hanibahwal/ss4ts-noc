from __future__ import annotations

from app.models.execution_runtime_observability import (
    RecoveryRuntimeObservability,
    RuntimeHealthStatus,
)


PROMETHEUS_CONTENT_TYPE = (
    "text/plain; version=0.0.4; charset=utf-8"
)


def _boolean_value(
    value: bool,
) -> int:
    return 1 if value else 0


def _metric(
    name: str,
    value: int | float,
) -> str:
    return f"{name} {value}"


def _help_and_type(
    name: str,
    help_text: str,
    metric_type: str = "gauge",
) -> list[str]:
    return [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} {metric_type}",
    ]


def render_runtime_prometheus_metrics(
    metrics: RecoveryRuntimeObservability,
    *,
    metrics_version: int = 0,
) -> str:
    """
    Render runtime observability using Prometheus text exposition.

    Rendering is side-effect free. It does not persist metrics, start
    the scheduler runtime, contact managed devices, or perform network
    I/O.
    """

    if not isinstance(
        metrics,
        RecoveryRuntimeObservability,
    ):
        raise TypeError(
            "metrics must be a "
            "RecoveryRuntimeObservability"
        )

    normalized_version = max(
        0,
        int(metrics_version),
    )

    lines: list[str] = []

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_enabled",
            (
                "Whether the recovery scheduler runtime "
                "is enabled by environment configuration."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_enabled",
            _boolean_value(
                metrics.runtime_enabled
            ),
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_running",
            (
                "Whether the recovery scheduler runtime "
                "is currently running."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_running",
            _boolean_value(
                metrics.runtime_running
            ),
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_scheduler_enabled",
            (
                "Whether the persistent recovery "
                "scheduler is enabled."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_scheduler_enabled",
            _boolean_value(
                metrics.scheduler_enabled
            ),
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_scheduler_due",
            (
                "Whether the persistent recovery "
                "scheduler is currently due to run."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_scheduler_due",
            _boolean_value(
                metrics.scheduler_due
            ),
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_health_status",
            (
                "Runtime health represented as one-hot "
                "status labels."
            ),
        )
    )

    for status in (
        RuntimeHealthStatus.DISABLED,
        RuntimeHealthStatus.HEALTHY,
        RuntimeHealthStatus.DEGRADED,
        RuntimeHealthStatus.UNHEALTHY,
    ):
        lines.append(
            (
                "ss4ts_runtime_health_status"
                f'{{status="{status.value}"}} '
                f"{1 if metrics.health_status == status else 0}"
            )
        )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_cycle_count",
            (
                "Total number of runtime polling cycles."
            ),
            metric_type="counter",
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_cycle_count",
            metrics.cycle_count,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_successful_cycles_total",
            (
                "Total number of successfully completed "
                "runtime cycles."
            ),
            metric_type="counter",
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_successful_cycles_total",
            metrics.successful_cycle_count,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_failed_cycles_total",
            (
                "Total number of failed runtime cycles."
            ),
            metric_type="counter",
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_failed_cycles_total",
            metrics.failed_cycle_count,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_cycle_success_rate_percent",
            (
                "Percentage of runtime cycles that "
                "completed successfully."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_cycle_success_rate_percent",
            metrics.cycle_success_rate_percent,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_last_cycle_duration_seconds",
            (
                "Duration of the most recently completed "
                "runtime cycle."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_last_cycle_duration_seconds",
            (
                metrics.last_cycle_duration_seconds
                if (
                    metrics
                    .last_cycle_duration_seconds
                    is not None
                )
                else 0.0
            ),
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_last_recovered_count",
            (
                "Number of recoveries completed during "
                "the most recent scheduler result."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_last_recovered_count",
            metrics.last_recovered_count,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_last_skipped_count",
            (
                "Number of recoveries skipped during "
                "the most recent scheduler result."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_last_skipped_count",
            metrics.last_skipped_count,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_last_failed_count",
            (
                "Number of recovery failures during "
                "the most recent scheduler result."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_last_failed_count",
            metrics.last_failed_count,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_last_processed_count",
            (
                "Total number of recovery records handled "
                "during the most recent scheduler result."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_last_processed_count",
            metrics.last_processed_count,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_metrics_version",
            (
                "Version of the most recently persisted "
                "runtime observability snapshot."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_metrics_version",
            normalized_version,
        )
    )

    lines.extend(
        _help_and_type(
            "ss4ts_runtime_last_error",
            (
                "Whether the runtime currently has a "
                "recorded error."
            ),
        )
    )

    lines.append(
        _metric(
            "ss4ts_runtime_last_error",
            _boolean_value(
                metrics.last_error is not None
            ),
        )
    )

    return (
        "\n".join(lines)
        + "\n"
    )
