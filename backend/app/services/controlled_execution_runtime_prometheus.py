from __future__ import annotations

from typing import Any

from app.services.controlled_execution_runtime_observability import (
    ControlledRuntimeHealthStatus,
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
    *,
    metric_type: str = "gauge",
) -> list[str]:
    return [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} {metric_type}",
    ]


def render_controlled_runtime_prometheus(
    snapshot: dict[str, Any],
) -> str:
    """
    Render controlled-runtime metrics in Prometheus text format.

    Rendering is read-only and performs no persistence, network I/O,
    runtime lifecycle changes, or device command execution.
    """
    if not isinstance(
        snapshot,
        dict,
    ):
        raise TypeError(
            "snapshot must be a dictionary"
        )

    runtime = snapshot.get(
        "runtime",
        {},
    )

    metrics = snapshot.get(
        "metrics",
        {},
    )

    configuration = snapshot.get(
        "configuration",
        {},
    )

    health_status = str(
        runtime.get(
            "health_status",
            "unhealthy",
        )
    )

    lines: list[str] = []

    definitions = [
        (
            "ss4ts_controlled_recovery_runtime_enabled",
            (
                "Whether the controlled recovery runtime "
                "is enabled by environment configuration."
            ),
            _boolean_value(
                bool(
                    runtime.get(
                        "environment_enabled",
                        False,
                    )
                )
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_runtime_running",
            (
                "Whether the controlled recovery runtime "
                "is currently running."
            ),
            _boolean_value(
                bool(
                    runtime.get(
                        "running",
                        False,
                    )
                )
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_cycles_total",
            (
                "Total controlled recovery runtime cycles."
            ),
            int(
                metrics.get(
                    "cycle_count",
                    0,
                )
            ),
            "counter",
        ),
        (
            "ss4ts_controlled_recovery_successful_cycles_total",
            (
                "Total successful controlled recovery "
                "runtime cycles."
            ),
            int(
                metrics.get(
                    "successful_cycle_count",
                    0,
                )
            ),
            "counter",
        ),
        (
            "ss4ts_controlled_recovery_failed_cycles_total",
            (
                "Total failed controlled recovery "
                "runtime cycles."
            ),
            int(
                metrics.get(
                    "failed_cycle_count",
                    0,
                )
            ),
            "counter",
        ),
        (
            "ss4ts_controlled_recovery_recovered_total",
            (
                "Total records recovered by the controlled "
                "recovery runtime."
            ),
            int(
                metrics.get(
                    "total_recovered_count",
                    0,
                )
            ),
            "counter",
        ),
        (
            "ss4ts_controlled_recovery_last_recovered_count",
            (
                "Records recovered during the most recent "
                "runtime cycle."
            ),
            int(
                metrics.get(
                    "last_recovered_count",
                    0,
                )
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_cycle_success_rate_percent",
            (
                "Percentage of controlled recovery cycles "
                "that completed successfully."
            ),
            float(
                metrics.get(
                    "cycle_success_rate_percent",
                    0.0,
                )
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_last_cycle_duration_seconds",
            (
                "Duration of the most recently completed "
                "controlled recovery cycle."
            ),
            float(
                runtime.get(
                    "last_cycle_duration_seconds",
                    0.0,
                )
                or 0.0
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_last_cycle_age_seconds",
            (
                "Age of the most recently completed "
                "controlled recovery cycle."
            ),
            float(
                runtime.get(
                    "last_cycle_age_seconds",
                    0.0,
                )
                or 0.0
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_last_error",
            (
                "Whether the controlled recovery runtime "
                "currently has a recorded error."
            ),
            _boolean_value(
                runtime.get(
                    "last_error"
                )
                is not None
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_interval_seconds",
            (
                "Configured controlled recovery runtime "
                "interval."
            ),
            float(
                configuration.get(
                    "interval_seconds",
                    0.0,
                )
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_stale_after_seconds",
            (
                "Configured controlled recovery stale "
                "threshold."
            ),
            int(
                configuration.get(
                    "stale_after_seconds",
                    0,
                )
            ),
            "gauge",
        ),
        (
            "ss4ts_controlled_recovery_batch_limit",
            (
                "Configured controlled recovery batch "
                "limit."
            ),
            int(
                configuration.get(
                    "limit",
                    0,
                )
            ),
            "gauge",
        ),
    ]

    for (
        name,
        help_text,
        value,
        metric_type,
    ) in definitions:
        lines.extend(
            _help_and_type(
                name,
                help_text,
                metric_type=metric_type,
            )
        )

        lines.append(
            _metric(
                name,
                value,
            )
        )

    health_metric = (
        "ss4ts_controlled_recovery_health_status"
    )

    lines.extend(
        _help_and_type(
            health_metric,
            (
                "Controlled recovery runtime health "
                "represented as one-hot status labels."
            ),
        )
    )

    for status in (
        ControlledRuntimeHealthStatus.DISABLED,
        ControlledRuntimeHealthStatus.HEALTHY,
        ControlledRuntimeHealthStatus.DEGRADED,
        ControlledRuntimeHealthStatus.UNHEALTHY,
    ):
        lines.append(
            (
                f'{health_metric}'
                f'{{status="{status.value}"}} '
                f"{1 if health_status == status.value else 0}"
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    )
