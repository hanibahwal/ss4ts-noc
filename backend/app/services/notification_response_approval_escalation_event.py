from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class EscalationEventStatus(str, Enum):

    CREATED = "CREATED"

    SENT = "SENT"

    FAILED = "FAILED"



@dataclass
class ApprovalEscalationEvent:

    event_id: str

    approval_id: str

    escalation_level: str

    target: str

    risk_score: int

    message: str

    status: EscalationEventStatus

    created_at: datetime



class NotificationResponseApprovalEscalationEventPipeline:
    """
    SS4TS Approval Escalation Event Pipeline

    H23.4.5.5.12.22.13.7.8

    Responsibilities:

    - Create escalation events
    - Prepare executive messages
    - Track notification state
    """

    def create_event(
        self,
        decision,
    ) -> ApprovalEscalationEvent:


        message = self.build_message(
            decision
        )


        return ApprovalEscalationEvent(

            event_id=self._generate_id(),

            approval_id=decision.approval_id,

            escalation_level=decision.level.value,

            target=decision.target.value,

            risk_score=decision.risk_score,

            message=message,

            status=EscalationEventStatus.CREATED,

            created_at=datetime.now(
                timezone.utc
            ),
        )



    def build_message(
        self,
        decision,
    ) -> str:


        return f"""
🚨 SS4TS EXECUTIVE APPROVAL ALERT

Approval ID:
{decision.approval_id}

Risk Score:
{decision.risk_score}%

Escalation Level:
{decision.level.value}

Target:
{decision.target.value}

Reason:
{decision.reason}

Time:
{datetime.now(timezone.utc).isoformat()}
""".strip()



    def mark_sent(
        self,
        event: ApprovalEscalationEvent,
    ):

        event.status = (
            EscalationEventStatus.SENT
        )

        return event



    def mark_failed(
        self,
        event: ApprovalEscalationEvent,
    ):

        event.status = (
            EscalationEventStatus.FAILED
        )

        return event



    def _generate_id(
        self,
    ) -> str:

        import uuid

        return str(uuid.uuid4())



def create_escalation_event_pipeline():

    return (
        NotificationResponseApprovalEscalationEventPipeline()
    )
