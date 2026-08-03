from __future__ import annotations

from datetime import datetime, timezone

from app.models.notification_audit_decision import (
    NotificationAuditDecision,
    NotificationDecisionType,
)

from app.models.notification_audit_intelligence import (
    NotificationAuditRisk,
)



class NotificationAuditDecisionEngine:


    def calculate(
        self,
        risk: NotificationAuditRisk,
    ) -> NotificationAuditDecision:


        decision = (
            NotificationDecisionType.MONITOR
        )


        confidence = 90


        reason = (
            "Low risk activity"
        )


        actions = [
            "Continue monitoring"
        ]



        # ===============================
        # Critical Risk
        # ===============================

        if risk.risk_level.value == "critical":

            decision = (
                NotificationDecisionType.BLOCK
            )

            confidence = 97

            reason = (
                "Critical notification security risk"
            )

            actions = [

                "Block suspicious identity",

                "Escalate security incident",

                "Review notification permissions",

            ]



        # ===============================
        # High Risk
        # ===============================

        elif risk.risk_level.value == "high":

            decision = (
                NotificationDecisionType.ESCALATE
            )

            confidence = 90

            reason = (
                "High risk notification activity detected"
            )

            actions = [

                "Investigate identity activity",

                "Review access permissions",

                "Increase monitoring level",

            ]



        # ===============================
        # Medium Risk
        # ===============================

        elif risk.risk_level.value == "medium":

            decision = (
                NotificationDecisionType.INVESTIGATE
            )

            confidence = 85

            reason = (
                "Suspicious notification behavior detected"
            )

            actions = [

                "Review failed actions",

                "Analyze audit history",

            ]



        return NotificationAuditDecision(

            decision=decision,

            confidence=confidence,

            reason=reason,

            risk_level=risk.risk_level.value,

            risk_score=risk.risk_score,

            actions=actions,

            generated_at=datetime.now(
                timezone.utc
            ),

        )
