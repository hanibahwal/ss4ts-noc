from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.notification_response_approval import (
    ApprovalStatus,
    NotificationResponseApproval,
)

from app.services.notification_response_approval_escalation import (
    create_approval_escalation_engine,
)

from app.services.notification_response_approval_escalation_pipeline import (
    create_escalation_pipeline,
)



class NotificationResponseApprovalEscalationDemo:

    """
    H23.4.5.5.12.22.13.7.8.4

    Critical Approval Demo Flow
    """


    def __init__(self):

        self.engine = (
            create_approval_escalation_engine()
        )

        self.pipeline = (
            create_escalation_pipeline()
        )


    def execute(self):

        approval = NotificationResponseApproval(

            approval_id=str(uuid4()),

            execution_id=str(uuid4()),

            action_id="DEMO-FIREWALL-CHANGE",

            action_type="firewall_change",

            requested_reason=(
                "Demo critical firewall modification"
            ),

            status=ApprovalStatus.PENDING,

            approved_by=None,

            requested_at=datetime.now(
                timezone.utc
            ),

            approved_at=None,
        )


        risk_score = 95


        decision = self.engine.evaluate(

            approval,

            risk_score,

        )


        result = self.pipeline.process(

            decision

        )


        return {

            "approval_id":
                approval.approval_id,

            "risk_score":
                risk_score,

            "level":
                decision.level.value,

            "target":
                decision.target.value,

            "reason":
                decision.reason,

            "event_id":
                result.event_id,

            "telegram_sent":
                result.sent,

        }



def create_demo():

    return (
        NotificationResponseApprovalEscalationDemo()
    )
