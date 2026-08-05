from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


from app.models.notification_response_approval import (
    ApprovalStatus,
    NotificationResponseApproval,
)


from app.services.notification_response_approval_escalation_audit import (
    NotificationResponseApprovalEscalationAuditStore,
)



class EscalationLevel(str, Enum):

    LOW = "LOW"

    MEDIUM = "MEDIUM"

    HIGH = "HIGH"

    CRITICAL = "CRITICAL"



class EscalationTarget(str, Enum):

    NONE = "NONE"

    NOC = "NOC"

    SUPERVISOR = "SUPERVISOR"

    MANAGEMENT = "MANAGEMENT"



@dataclass
class ApprovalEscalationDecision:

    approval_id: str

    risk_score: int

    level: EscalationLevel

    target: EscalationTarget

    reason: str

    created_at: datetime



class NotificationResponseApprovalEscalationEngine:
    """
    SS4TS Approval Auto Escalation Engine

    H23.4.5.5.12.22.13.7.2

    Responsibilities:

    - Calculate escalation level
    - Select escalation target
    - Generate escalation decision
    - Write escalation audit trail

    """


    def __init__(
        self,
        audit_store: NotificationResponseApprovalEscalationAuditStore | None = None,
    ):

        self.audit_store = (
            audit_store
            or NotificationResponseApprovalEscalationAuditStore()
        )



    def evaluate_risk_level(
        self,
        risk_score: int,
    ) -> EscalationLevel:


        if risk_score >= 81:

            return EscalationLevel.CRITICAL


        if risk_score >= 61:

            return EscalationLevel.HIGH


        if risk_score >= 31:

            return EscalationLevel.MEDIUM


        return EscalationLevel.LOW




    def resolve_target(
        self,
        level: EscalationLevel,
    ) -> EscalationTarget:


        mapping = {

            EscalationLevel.LOW:
                EscalationTarget.NONE,


            EscalationLevel.MEDIUM:
                EscalationTarget.NOC,


            EscalationLevel.HIGH:
                EscalationTarget.SUPERVISOR,


            EscalationLevel.CRITICAL:
                EscalationTarget.MANAGEMENT,

        }


        return mapping[level]




    def build_reason(
        self,
        approval: NotificationResponseApproval,
        risk_score: int,
    ) -> str:


        reasons = []


        if approval.status == ApprovalStatus.PENDING:

            reasons.append(
                "Approval request still pending"
            )


        if risk_score >= 81:

            reasons.append(
                "Critical governance risk"
            )


        if approval.action_type in [

            "router_restart",

            "firewall_change",

            "network_shutdown",

        ]:

            reasons.append(
                "Critical infrastructure action"
            )



        if not reasons:

            reasons.append(
                "Risk threshold exceeded"
            )


        return ", ".join(
            reasons
        )




    def _notification_channel(
        self,
        target: EscalationTarget,
    ) -> str:


        mapping = {

            EscalationTarget.NONE:
                "none",

            EscalationTarget.NOC:
                "telegram_noc",

            EscalationTarget.SUPERVISOR:
                "telegram_supervisor",

            EscalationTarget.MANAGEMENT:
                "telegram_executive",

        }


        return mapping[target]




    def evaluate(
        self,
        approval: NotificationResponseApproval,
        risk_score: int,
    ) -> ApprovalEscalationDecision:



        level = self.evaluate_risk_level(
            risk_score
        )


        target = self.resolve_target(
            level
        )


        reason = self.build_reason(
            approval,
            risk_score,
        )


        decision = ApprovalEscalationDecision(

            approval_id=approval.approval_id,

            risk_score=risk_score,

            level=level,

            target=target,

            reason=reason,

            created_at=datetime.now(
                timezone.utc
            ),

        )



        #
        # H23.4.5.5.12.22.13.7.7.2
        #
        # Save escalation audit record
        #


        if target != EscalationTarget.NONE:


            self.audit_store.create_record(

                approval_id=approval.approval_id,

                execution_id=approval.execution_id,

                risk_score=risk_score,

                priority_before="NORMAL",

                priority_after=level.value,

                escalation_level=level.value.lower(),

                notification_channel=self._notification_channel(
                    target
                ),

                destination=target.value,

                notification_status="pending",

            )



        return decision




def create_approval_escalation_engine():


    return NotificationResponseApprovalEscalationEngine()
