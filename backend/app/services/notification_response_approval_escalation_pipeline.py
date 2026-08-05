from __future__ import annotations


from dataclasses import dataclass



from app.services.notification_response_approval_escalation_event import (
    create_escalation_event_pipeline,
)



from app.services.notification_response_approval_telegram import (
    create_telegram_adapter,
)



from app.services.notification_response_approval_escalation_audit_store import (
    NotificationResponseApprovalEscalationAuditStore,
)



@dataclass
class EscalationPipelineResult:

    event_id: str

    sent: bool

    target: str

    message: str

    audit_id: str | None




class NotificationResponseApprovalEscalationPipeline:
    """
    SS4TS Approval Escalation Pipeline

    H23.4.5.5.12.22.13.7.8.5.3

    Flow:

    Escalation Decision
            |
            v
    Event Creation
            |
            v
    Telegram Notification
            |
            v
    Escalation Audit Persistence
            |
            v
    Prometheus Metrics

    """



    def __init__(self):


        self.event_pipeline = (
            create_escalation_event_pipeline()
        )


        self.telegram = (
            create_telegram_adapter()
        )


        self.audit_store = (
            NotificationResponseApprovalEscalationAuditStore(
                "notifications.sqlite3"
            )
        )



    def process(
        self,
        decision,
    ) -> EscalationPipelineResult:



        #
        # Create escalation event
        #

        event = (
            self.event_pipeline.create_event(
                decision
            )
        )



        #
        # Send Telegram notification
        #

        notification = (
            self.telegram.send_event(
                event
            )
        )



        if notification.success:


            self.event_pipeline.mark_sent(
                event
            )


            telegram_status = "SENT"



        else:


            self.event_pipeline.mark_failed(
                event
            )


            telegram_status = "FAILED"





        #
        # Persist escalation audit
        #

        audit_id = (

            self.audit_store.save(

                decision,

                telegram_status,

            )

        )





        return EscalationPipelineResult(


            event_id=event.event_id,


            sent=notification.success,


            target=event.target,


            message=event.message,


            audit_id=audit_id,


        )




def create_escalation_pipeline():


    return (

        NotificationResponseApprovalEscalationPipeline()

    )
