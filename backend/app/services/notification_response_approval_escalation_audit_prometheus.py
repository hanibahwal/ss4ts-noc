from __future__ import annotations


from datetime import datetime, timezone



PROMETHEUS_CONTENT_TYPE = (
    "text/plain; version=0.0.4; charset=utf-8"
)



def _metric(
    name: str,
    value: int | float,
) -> str:

    return f"{name} {value}"



def _help_type(
    name: str,
    description: str,
    metric_type: str = "gauge",
) -> list[str]:

    return [

        f"# HELP {name} {description}",

        f"# TYPE {name} {metric_type}",

    ]



def _parse_timestamp(
    timestamp: str,
) -> float:

    try:

        return (
            datetime
            .fromisoformat(
                timestamp
            )
            .replace(
                tzinfo=timezone.utc
            )
            .timestamp()
        )

    except Exception:

        return 0



def render_notification_response_approval_escalation_audit_metrics(
    escalation_history: list[dict],
) -> str:
    """
    SS4TS Escalation Audit Prometheus Metrics

    H23.4.5.5.12.22.13.7.8.5.2

    Metrics:

    - Total escalation events
    - Critical escalations
    - Management escalations
    - Telegram success
    - Telegram failures
    - Last escalation timestamp

    """



    if not isinstance(
        escalation_history,
        list,
    ):

        raise TypeError(
            "escalation_history must be list"
        )



    total_events = len(
        escalation_history
    )



    critical_total = sum(

        1

        for item in escalation_history

        if item.get("level")
        == "CRITICAL"

    )



    management_total = sum(

        1

        for item in escalation_history

        if item.get("target")
        == "MANAGEMENT"

    )



    telegram_success = sum(

        1

        for item in escalation_history

        if item.get(
            "telegram_status"
        )
        in [
            "SENT",
            "SUCCESS",
        ]

    )



    telegram_failed = sum(

        1

        for item in escalation_history

        if item.get(
            "telegram_status"
        )
        in [
            "FAILED",
            "ERROR",
        ]

    )



    last_timestamp = 0


    if escalation_history:

        last_timestamp = max(

            _parse_timestamp(
                item.get(
                    "created_at",
                    "",
                )
            )

            for item in escalation_history

        )



    metrics = [

        (

            "ss4ts_notification_escalation_events_total",

            "Total escalation audit events",

            total_events,

        ),


        (

            "ss4ts_notification_escalation_critical_total",

            "Total critical escalation events",

            critical_total,

        ),


        (

            "ss4ts_notification_escalation_management_total",

            "Total management escalation events",

            management_total,

        ),


        (

            "ss4ts_notification_escalation_telegram_success_total",

            "Total successful Telegram escalation notifications",

            telegram_success,

        ),


        (

            "ss4ts_notification_escalation_telegram_failed_total",

            "Total failed Telegram escalation notifications",

            telegram_failed,

        ),


        (

            "ss4ts_notification_escalation_last_timestamp",

            "Last escalation event timestamp",

            last_timestamp,

        ),

    ]



    lines = []



    for name, description, value in metrics:


        lines.extend(

            _help_type(

                name,

                description,

            )

        )


        lines.append(

            _metric(

                name,

                value,

            )

        )



    return (
        "\n".join(lines)
        +
        "\n"
    )
