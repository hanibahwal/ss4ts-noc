from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.models.notification_audit import (
    NotificationAuditResult,
)

from app.models.notification_audit_intelligence import (
    AuditRiskLevel,
    NotificationAuditRisk,
)

from app.services.notification_audit import (
    NotificationAuditStore,
)



class NotificationAuditIntelligence:


    def __init__(
        self,
        store: NotificationAuditStore,
    ):

        self.store = store



    def calculate(
        self,
    ) -> NotificationAuditRisk:


        records = (
            self.store.list_audits()
        )


        total_events = len(records)


        success_events = sum(
            1
            for item in records
            if item.result
            == NotificationAuditResult.SUCCESS
        )


        failed_events = sum(
            1
            for item in records
            if item.result
            == NotificationAuditResult.FAILED
        )


        denied_events = sum(
            1
            for item in records
            if item.result
            == NotificationAuditResult.DENIED
        )


        identity_counter = Counter(
            item.identity_id
            for item in records
        )


        top_identity = None

        if identity_counter:
            top_identity = (
                identity_counter
                .most_common(1)[0][0]
            )


        risk_score = 0



        # Failed events impact
        risk_score += (
            failed_events * 5
        )



        # Permission denied impact
        risk_score += (
            denied_events * 3
        )



        # Repeated identity activity
        if top_identity:

            top_count = (
                identity_counter[
                    top_identity
                ]
            )

            if top_count >= 10:
                risk_score += 20

            elif top_count >= 5:
                risk_score += 10



        # High activity volume
        if total_events >= 50:

            risk_score += 15

        elif total_events >= 20:

            risk_score += 5



        # Maximum score
        risk_score = min(
            risk_score,
            100,
        )



        risk_level = (
            self._calculate_level(
                risk_score
            )
        )


        recommendations = (
            self._recommendations(
                risk_level,
                failed_events,
                denied_events,
            )
        )



        return NotificationAuditRisk(

            risk_score=risk_score,

            risk_level=risk_level,

            total_events=total_events,

            failed_events=failed_events,

            denied_events=denied_events,

            success_events=success_events,

            top_identity=top_identity,

            recommendations=recommendations,

            generated_at=datetime.now(
                timezone.utc
            ),

        )




    def _calculate_level(
        self,
        score: int,
    ) -> AuditRiskLevel:


        if score >= 81:

            return AuditRiskLevel.CRITICAL


        if score >= 61:

            return AuditRiskLevel.HIGH


        if score >= 31:

            return AuditRiskLevel.MEDIUM


        return AuditRiskLevel.LOW




    def _recommendations(
        self,
        level: AuditRiskLevel,
        failed: int,
        denied: int,
    ) -> list[str]:


        recommendations = []


        if level in (
            AuditRiskLevel.HIGH,
            AuditRiskLevel.CRITICAL,
        ):

            recommendations.append(
                "Review execution permissions"
            )


        if failed > 0:

            recommendations.append(
                "Investigate failed actions"
            )


        if denied > 0:

            recommendations.append(
                "Review denied access attempts"
            )


        if not recommendations:

            recommendations.append(
                "No immediate action required"
            )


        return recommendations
