from __future__ import annotations

from datetime import datetime, timezone

from app.models.notification_response_approval import (
    ApprovalStatus,
    NotificationResponseApproval,
)


class NotificationResponseApprovalIntelligence:

    """
    H23.4.5.5.12.22.13.6

    Approval Governance Intelligence Engine

    Responsibilities:
    - Risk Score calculation
    - Priority classification
    - Aging analytics
    - SLA evaluation
    """


    def calculate_risk_score(
        self,
        approval: NotificationResponseApproval,
    ) -> int:

        score = 0


        # Pending age factor
        age_seconds = (
            datetime.now(timezone.utc)
            -
            approval.requested_at
        ).total_seconds()


        if age_seconds > 3600:
            score += 40

        elif age_seconds > 1800:
            score += 20


        # Status factor

        if approval.status == ApprovalStatus.PENDING:
            score += 20


        # Action criticality

        critical_actions = [
            "router_restart",
            "firewall_change",
            "network_shutdown",
        ]


        if approval.action_type in critical_actions:
            score += 40


        return min(score, 100)



    def classify_priority(
        self,
        risk_score: int,
    ) -> int:

        """
        Priority:

        1 Emergency
        2 Critical
        3 High
        4 Normal
        5 Low
        """

        if risk_score >= 80:
            return 1

        if risk_score >= 60:
            return 2

        if risk_score >= 40:
            return 3

        if risk_score >= 20:
            return 4

        return 5



    def calculate_age_seconds(
        self,
        approval: NotificationResponseApproval,
    ) -> float:


        return (
            datetime.now(timezone.utc)
            -
            approval.requested_at
        ).total_seconds()



    def escalation_level(
        self,
        age_seconds: float,
    ) -> str:


        if age_seconds >= 14400:
            return "MANAGEMENT"


        if age_seconds >= 3600:
            return "SUPERVISOR"


        if age_seconds >= 900:
            return "NOC"


        return "NORMAL"
