from __future__ import annotations

from datetime import datetime, timezone


def _metric(
    name: str,
    value: int | float,
) -> str:

    return f"{name} {value}"



def _help(
    name: str,
    description: str,
) -> list[str]:

    return [
        f"# HELP {name} {description}",
        f"# TYPE {name} gauge",
    ]



def render_notification_response_approval_escalation_metrics(
    escalation_history: list[dict],
) -> str:
    """
    H23.4.5.5.12.22.13.7.3

    Prometheus metrics for Approval Auto Escalation Engine
    """


    if not isinstance(
        escalation_history,
        list,
    ):
        raise TypeError(
            "escalation_history must be list"
        )


    total = len(
        escalation_history
    )


    critical = sum(
        1
        for item in escalation_history
        if item.get("level")
        == "CRITICAL"
    )


    noc_alerts = sum(
        1
        for item in escalation_history
        if item.get("target")
        == "NOC"
    )


    management_alerts = sum(
        1
        for item in escalation_history
        if item.get("target")
        == "MANAGEMENT"
    )


    last_timestamp = 0


    if escalation_history:

        latest = escalation_history[0]

        created = datetime.fromisoformat(
            latest["created_at"]
        )

        last_timestamp = (
            created.timestamp()
        )



    metrics = [

        (
            "ss4ts_notification_approval_escalation_total",
            "Total approval escalation events",
            total,
        ),


        (
            "ss4ts_notification_approval_escalation_critical_total",
            "Total critical approval escalations",
            critical,
        ),


        (
            "ss4ts_notification_approval_noc_alerts_total",
            "Total NOC escalation notifications",
            noc_alerts,
        ),


        (
            "ss4ts_notification_approval_management_alerts_total",
            "Total management escalation notifications",
            management_alerts,
        ),


        (
            "ss4ts_notification_approval_last_escalation_timestamp",
            "Last approval escalation timestamp",
            last_timestamp,
        ),

    ]


    lines = []


    for name, description, value in metrics:

        lines.extend(
            _help(
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


    return "\n".join(lines) + "\n"
