from __future__ import annotations

import os

from datetime import datetime, timezone

from app.models.notification_response_approval import (
    ApprovalStatus,
    NotificationResponseApproval,
)

from app.services.notification_response_approval_demo import (
    generate_demo_approvals,
)


PROMETHEUS_CONTENT_TYPE = (
    "text/plain; version=0.0.4; charset=utf-8"
)


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


def _age_seconds(
    approval: NotificationResponseApproval,
) -> float:

    return (
        datetime.now(timezone.utc)
        -
        approval.requested_at
    ).total_seconds()


def _risk_score(
    approval: NotificationResponseApproval,
) -> int:

    score = 0

    age = _age_seconds(approval)

    if age > 86400:
        score += 60

    elif age > 21600:
        score += 40

    elif age > 3600:
        score += 20


    if approval.status == ApprovalStatus.PENDING:
        score += 20


    critical_actions = [
        "router_restart",
        "firewall_change",
        "network_shutdown",
        "emergency-response",
    ]


    if approval.action_type in critical_actions:
        score += 40


    return min(score, 100)


def render_notification_response_approval_prometheus_metrics(
    approvals: list[NotificationResponseApproval],
) -> str:


    if not isinstance(approvals, list):
        raise TypeError(
            "approvals must be a list"
        )


    #
    # H23.4.5.5.12.22.13.7
    # Synthetic Approval Demo Mode
    #
    # Enable:
    # SS4TS_APPROVAL_DEMO_MODE=true
    #
    if os.getenv(
        "SS4TS_APPROVAL_DEMO_MODE"
    ) == "true":

        approvals = generate_demo_approvals()



    pending = [
        item
        for item in approvals
        if item.status == ApprovalStatus.PENDING
    ]


    approved = sum(
        1
        for item in approvals
        if item.status == ApprovalStatus.APPROVED
    )


    rejected = sum(
        1
        for item in approvals
        if item.status == ApprovalStatus.REJECTED
    )


    expired = sum(
        1
        for item in approvals
        if item.status == ApprovalStatus.EXPIRED
    )


    total = len(approvals)


    approval_rate = (
        round(
            (approved / total) * 100,
            2,
        )
        if total
        else 0
    )


    pending_age_values = [
        _age_seconds(item)
        for item in pending
    ]


    oldest_pending_age = (
        max(pending_age_values)
        if pending_age_values
        else 0
    )


    average_age = (
        sum(pending_age_values)
        /
        len(pending_age_values)
        if pending_age_values
        else 0
    )


    risk_score = (
        max(
            [
                _risk_score(item)
                for item in pending
            ]
        )
        if pending
        else 0
    )


    sla_compliance = (
        round(
            (
                sum(
                    1
                    for item in pending
                    if _age_seconds(item) <= 3600
                )
                /
                len(pending)
            )
            *
            100,
            2,
        )
        if pending
        else 100
    )



    metrics = [

        (
            "ss4ts_notification_approval_requests_total",
            "Total notification approval requests",
            total,
        ),

        (
            "ss4ts_notification_approval_pending_total",
            "Pending approval requests",
            len(pending),
        ),

        (
            "ss4ts_notification_approval_approved_total",
            "Approved requests",
            approved,
        ),

        (
            "ss4ts_notification_approval_rejected_total",
            "Rejected requests",
            rejected,
        ),

        (
            "ss4ts_notification_approval_expired_total",
            "Expired requests",
            expired,
        ),

        (
            "ss4ts_notification_approval_rate_percent",
            "Approval success percentage",
            approval_rate,
        ),

        (
            "ss4ts_notification_approval_pending_age_seconds",
            "Oldest pending approval age in seconds",
            round(oldest_pending_age, 2),
        ),

        (
            "ss4ts_notification_approval_average_age_seconds",
            "Average approval age seconds",
            round(average_age, 2),
        ),

        (
            "ss4ts_notification_approval_oldest_age_seconds",
            "Oldest approval age seconds",
            round(oldest_pending_age, 2),
        ),

        (
            "ss4ts_notification_approval_risk_score",
            "Maximum approval governance risk score",
            risk_score,
        ),

        (
            "ss4ts_notification_approval_sla_compliance_percent",
            "Approval SLA compliance percentage",
            sla_compliance,
        ),

    ]


    lines = []


    for name, description, value in metrics:

        lines.extend(
            _help_and_type(
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
