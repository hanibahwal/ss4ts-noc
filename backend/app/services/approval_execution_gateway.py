from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


from app.services.remediation_approval_service import (
    approve_request,
    get_approval_by_id,
)


from app.services.autonomous_remediation_controller import (
    execute_approved_remediation,
)



SERVICE_NAME = (
    "SS4TS Approval Execution Gateway"
)


SERVICE_VERSION = (
    "1.2.0-autonomous-remediation-bridge"
)





def _utc_now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()





def execute_approved_action(
    *,
    approval_id: str,
) -> dict[str, Any]:
    """
    H23.4.5.5.12.X.4.10

    Approval Execution Gateway

    Flow:

    AI Decision
          |
          v
    Human Approval
          |
          v
    Execution Gateway
          |
          v
    Autonomous Remediation Controller
          |
          v
    Execution Result


    Features:

    - Approval Validation
    - Human Authorization Check
    - Safe Execution Trigger
    - Remediation Controller Bridge
    - Execution Tracking

    """



    approval = get_approval_by_id(
        approval_id
    )



    if not approval:


        return {

            "engine": {

                "name":
                    SERVICE_NAME,

                "version":
                    SERVICE_VERSION,

            },


            "status":
                "FAILED",


            "reason":
                "Approval request not found",


            "approval_id":
                approval_id,


            "generated_at":
                _utc_now(),

        }





    current_status = (
        approval.get(
            "status"
        )
    )



    if current_status != "WAITING_APPROVAL":


        return {

            "engine": {

                "name":
                    SERVICE_NAME,


                "version":
                    SERVICE_VERSION,

            },


            "status":
                "FAILED",


            "reason":
                "Approval already processed",


            "approval":
                approval,


            "generated_at":
                _utc_now(),

        }





    #
    # Human Approval
    #

    approved = approve_request(
        approval_id
    )



    if not approved or approved.get(
        "success"
    ) is False:


        return {

            "engine": {

                "name":
                    SERVICE_NAME,


                "version":
                    SERVICE_VERSION,

            },


            "status":
                "FAILED",


            "reason":
                "Approval execution failed",


            "approval":
                approved,


            "generated_at":
                _utc_now(),

        }





    #
    # Send approved action
    # to Autonomous Remediation Controller
    #

    execution_result = (
        execute_approved_remediation(
            approval=approved
        )
    )





    return {


        "engine": {

            "name":
                SERVICE_NAME,


            "version":
                SERVICE_VERSION,

        },



        "status":
            "SUCCESS",



        "approval":

            approved,



        "execution": {


            "status":
                "SUBMITTED",



            "controller":
                "AUTONOMOUS_REMEDIATION_CONTROLLER",



            "result":
                execution_result,


        },



        "next_step":

            "WAIT_EXECUTION_RESULT",



        "generated_at":
            _utc_now(),


    }
