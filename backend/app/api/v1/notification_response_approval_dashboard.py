from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends


from app.api.v1.notification_security import (
    require_notification_permission,
)


from app.models.notification_permission import (
    NotificationPermission,
)


from app.services.notification_response_approval import (
    NotificationResponseApprovalStore,
)


from app.services.notification_response_approval_binding import (
    NotificationResponseApprovalBindingStore,
)


from app.services.notification_response_execution_history import (
    NotificationResponseExecutionHistoryStore,
)



DATABASE = Path(
    "notifications.sqlite3"
)



router = APIRouter(
    prefix="/notifications/audit/response/approval/dashboard",
    tags=[
        "notification-response-dashboard"
    ],
)



def get_approval_store():

    return NotificationResponseApprovalStore(
        DATABASE
    )



def get_binding_store():

    return NotificationResponseApprovalBindingStore(
        DATABASE
    )



def get_execution_history_store():

    return NotificationResponseExecutionHistoryStore(
        DATABASE
    )



@router.get(
    "/summary",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def summary():


    approval_store = get_approval_store()


    pending = approval_store.pending()


    return {

        "total_pending":
            len(pending),


        "high_risk":
            0,


        "medium_risk":
            0,


        "low_risk":
            len(pending),


        "approved_today":
            0,


        "rejected_today":
            0,

    }



@router.get(
    "/pending",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def pending():


    store = get_approval_store()


    return [

        item.to_dict()

        for item in store.pending()

    ]



@router.get(
    "/{approval_id}/timeline",
    dependencies=[
        Depends(
            require_notification_permission(
                NotificationPermission.READ
            )
        )
    ],
)
def timeline(
    approval_id: str,
):


    binding_store = get_binding_store()

    execution_store = get_execution_history_store()


    events = []



    bindings = binding_store.list_history(
        100
    )



    for item in bindings:


        if item.approval_id != approval_id:

            continue



        timestamp = (
            item.created_at.isoformat()
        )



        #
        # Approval Requested
        #

        events.append(

            {

                "type":
                    "approval",


                "status":
                    "requested",


                "timestamp":
                    timestamp,

            }

        )



        #
        # Approval Completed
        #

        if item.status.value == "completed":


            events.append(

                {

                    "type":
                        "approval",


                    "status":
                        "approved",


                    "timestamp":
                        timestamp,

                }

            )



        #
        # Execution Lifecycle
        #

        if item.execution_id:


            executions = (
                execution_store.list_history(
                    100
                )
            )



            for execution in executions:


                data = (
                    execution.to_dict()
                )


                if (
                    data.get(
                        "execution_id"
                    )
                    != item.execution_id
                ):

                    continue



                execution_timestamp = (
                    data.get(
                        "created_at"
                    )
                )



                events.append(

                    {

                        "type":
                            "execution",


                        "status":
                            "started",


                        "execution_id":
                            item.execution_id,


                        "timestamp":
                            execution_timestamp,

                    }

                )



                events.append(

                    {

                        "type":
                            "execution",


                        "status":
                            "completed",


                        "execution_id":
                            item.execution_id,


                        "timestamp":
                            execution_timestamp,

                    }

                )



    return {

        "approval_id":
            approval_id,


        "events":
            events,

    }
