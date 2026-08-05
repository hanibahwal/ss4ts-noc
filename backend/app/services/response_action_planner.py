from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid


from app.services.remediation_approval_service import (
    create_approval_request,
)



SERVICE_NAME = (
    "SS4TS AI Response Action Planner"
)


SERVICE_VERSION = (
    "1.3.0-approval-workflow-production"
)



def _utc_now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()



def generate_response_plan(
    *,
    executive_decision: dict[str, Any],
    router_ip: str,
) -> dict[str, Any]:
    """
    SS4TS AI Response Action Planner

    Converts Executive Decision into
    safe response workflow.

    H23.4.5.5.12.X.4.7

    Features:

    - AI Action Planning
    - Human Approval Workflow
    - Unique Approval ID per Action
    - Safe Execution Pipeline
    - Remediation Ready

    """


    now = _utc_now()



    decision_data = (
        executive_decision.get(
            "decision",
            {}
        )
    )



    decision = (
        decision_data.get(
            "decision",
            "UNKNOWN"
        )
    )



    priority = (
        decision_data.get(
            "priority",
            "LOW"
        )
    )



    approval_required = (
        decision_data.get(
            "approval_required",
            False
        )
    )



    #
    # No action required
    #

    if decision == "CONTINUE_MONITORING":


        return {

            "engine": {

                "name":
                    SERVICE_NAME,


                "version":
                    SERVICE_VERSION,

            },


            "router_ip":
                router_ip,


            "decision":
                decision,


            "priority":
                priority,


            "approval_required":
                False,


            "status":
                "NO_ACTION_REQUIRED",


            "action_count":
                0,


            "actions":
                [],


            "approval_requests":
                [],


            "generated_at":
                now,

        }



    actions = []



    #
    # CPU Optimization Workflow
    #

    if decision == "OPTIMIZE_CPU_LOAD":


        actions = [

            {

                "action_id":
                    str(uuid.uuid4()),


                "action_type":
                    "CHECK_CPU_PROCESS",


                "description":
                    "Analyze high CPU consuming processes",


                "risk_level":
                    "LOW",


                "priority":
                    priority,


                "status":
                    "WAITING_APPROVAL",

            },


            {

                "action_id":
                    str(uuid.uuid4()),


                "action_type":
                    "CHECK_FIREWALL_LOAD",


                "description":
                    "Review firewall and connection tracking load",


                "risk_level":
                    "MEDIUM",


                "priority":
                    priority,


                "status":
                    "WAITING_APPROVAL",

            },


            {

                "action_id":
                    str(uuid.uuid4()),


                "action_type":
                    "ANALYZE_TRAFFIC_LOAD",


                "description":
                    "Analyze traffic utilization patterns",


                "risk_level":
                    "LOW",


                "priority":
                    priority,


                "status":
                    "WAITING_APPROVAL",

            },

        ]


    else:


        actions = [

            {

                "action_id":
                    str(uuid.uuid4()),


                "action_type":
                    decision,


                "description":
                    "Execute recommended AI action",


                "risk_level":
                    "MEDIUM",


                "priority":
                    priority,


                "status":
                    "WAITING_APPROVAL",

            }

        ]



        #
    # Human Approval Integration
    #

    approval_requests = []


    if approval_required:


        for action in actions:


            approval = create_approval_request(

                router_ip=
                    router_ip,

                action_type=
                    action["action_type"],

                reason=
                    action["description"],

                priority=
                    action["priority"],

            )


            action["approval_id"] = (
    approval.get("approval", {})
    .get("approval_id")
)

            approval_requests.append(
                approval
            )



    return {


        "engine": {

            "name":
                SERVICE_NAME,


            "version":
                SERVICE_VERSION,

        },


        "router_ip":
            router_ip,


        "decision":
            decision,


        "priority":
            priority,


        "approval_required":
            approval_required,


        "status":

            (
                "WAITING_APPROVAL"
                if approval_required
                else
                "READY"
            ),



        "action_count":
            len(actions),



        "actions":
            actions,



        "approval_requests":
            approval_requests,



        "generated_at":
            now,


    }
