from __future__ import annotations


from datetime import datetime


from fastapi import (
    APIRouter,
    HTTPException,
)


from fastapi.responses import (
    PlainTextResponse,
)



from app.models.notification_response_approval import (
    ApprovalStatus,
    NotificationResponseApproval,
)



from app.services.notification_response_approval import (
    NotificationResponseApprovalStore,
)



from app.services.notification_response_approval_prometheus import (
    PROMETHEUS_CONTENT_TYPE,
    render_notification_response_approval_prometheus_metrics,
)



from app.services.notification_response_approval_escalation_prometheus import (
    render_notification_response_approval_escalation_metrics,
)



from app.services.notification_response_approval_escalation_store import (
    NotificationResponseApprovalEscalationStore,
)



from app.services.notification_response_approval_escalation_audit_store import (
    NotificationResponseApprovalEscalationAuditStore,
)



from app.services.notification_response_approval_escalation_audit_prometheus import (
    render_notification_response_approval_escalation_audit_metrics,
)



from app.services.notification_response_approval_escalation_demo import (
    create_demo,
)



router = APIRouter(
    prefix="/notifications/audit/response/approval",
    tags=[
        "notification-response-approval-prometheus"
    ],
)



def get_approval_store():

    return NotificationResponseApprovalStore(
        "notifications.sqlite3"
    )



def get_escalation_store():

    return NotificationResponseApprovalEscalationStore(
        "notifications.sqlite3"
    )



def get_escalation_audit_store():

    return NotificationResponseApprovalEscalationAuditStore(
        "notifications.sqlite3"
    )



def _convert_history_to_models(
    history: list[dict],
) -> list[NotificationResponseApproval]:

    approvals: list[NotificationResponseApproval] = []


    for item in history:

        approvals.append(

            NotificationResponseApproval(

                approval_id=item["approval_id"],

                execution_id=item["execution_id"],

                action_id=item["action_id"],

                action_type=item["action_type"],

                requested_reason=item["requested_reason"],

                status=ApprovalStatus(
                    item["status"]
                ),

                approved_by=item["approved_by"],

                requested_at=datetime.fromisoformat(
                    item["requested_at"]
                ),

                approved_at=(

                    datetime.fromisoformat(
                        item["approved_at"]
                    )

                    if item["approved_at"]

                    else None

                ),
            )
        )


    return approvals




@router.get(
    "/prometheus",
    response_class=PlainTextResponse,
)
async def notification_response_approval_prometheus():

    try:


        #
        # =====================================================
        # Approval Governance Metrics
        # =====================================================
        #

        approval_store = get_approval_store()



        history = approval_store.list_history(
            limit=1000
        )



        approvals = _convert_history_to_models(
            history
        )



        content = (

            render_notification_response_approval_prometheus_metrics(

                approvals

            )

        )



        #
        # =====================================================
        # Auto Escalation Metrics
        # =====================================================
        #

        escalation_store = get_escalation_store()



        escalation_history = (

            escalation_store.get_history(

                limit=1000

            )

        )



        content += "\n"



        content += (

            render_notification_response_approval_escalation_metrics(

                escalation_history

            )

        )




        #
        # =====================================================
        # Escalation Audit Metrics
        # =====================================================
        #

        audit_store = get_escalation_audit_store()



        audit_history = (

            audit_store.history(

                limit=1000

            )

        )



        content += "\n"



        content += (

            render_notification_response_approval_escalation_audit_metrics(

                audit_history

            )

        )



    except (

        OSError,

        RuntimeError,

        TypeError,

        ValueError,

        AttributeError,

    ) as exc:


        raise HTTPException(

            status_code=503,

            detail=str(exc),

        ) from exc



    return PlainTextResponse(

        content=content,

        media_type=PROMETHEUS_CONTENT_TYPE,

    )




#
# ==========================================================
# H23.4.5.5.12.22.13.7.8.4
# Critical Approval Escalation Demo Endpoint
# ==========================================================
#


@router.post(
    "/demo-critical-escalation",
)
async def demo_critical_escalation():

    try:


        demo = create_demo()



        result = demo.execute()



        return result



    except (

        OSError,

        RuntimeError,

        TypeError,

        ValueError,

        AttributeError,

    ) as exc:


        raise HTTPException(

            status_code=503,

            detail=str(exc),

        ) from exc
