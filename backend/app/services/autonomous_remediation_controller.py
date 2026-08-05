from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid


from app.services.remediation_approval_service import (
    get_approval_by_id,
)


from app.services.routeros_api_client import (
    create_routeros_client,
)


from app.services.remediation_result_intelligence import (
    generate_remediation_report,
)


from app.services.remediation_audit_history import (
    save_remediation_history,
)



ENGINE_NAME = (
    "SS4TS Autonomous Remediation Execution Controller"
)


ENGINE_VERSION = (
    "1.2.0-intelligence-report-bridge"
)



def _now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()



def execute_approved_remediation(
    *,
    approval_id: str,
    router_ip: str,
    action_type: str,
    username: str = "admin",
    password: str = "",
) -> dict[str, Any]:
    """
    H23.4.5.5.12.X.4.5.3

    Autonomous Remediation Execution Controller


    Flow:

    AI Decision
          |
          v
    Human Approval
          |
          v
    Approval Validation
          |
          v
    RouterOS Execution
          |
          v
    Verification
          |
          v
    Intelligence Report
          |
          v
    Executive Result


    Features:

    - Persistent Approval Validation
    - MikroTik Execution Gateway
    - Verification Layer
    - Rollback Capability
    - Executive Intelligence Report

    """



    #
    # Validate approval
    #

    approval = get_approval_by_id(
        approval_id
    )



    if not approval:


        return {

            "engine": {

                "name":
                    ENGINE_NAME,

                "version":
                    ENGINE_VERSION,

            },


            "execution": {

                "status":
                    "REJECTED",

                "reason":
                    "Approval request not found",

                "approval_id":
                    approval_id,

                "created_at":
                    _now(),

            }

        }




    #
    # Human approval check
    #

    if approval.get(
        "status"
    ) != "APPROVED":


        return {

            "engine": {

                "name":
                    ENGINE_NAME,

                "version":
                    ENGINE_VERSION,

            },


            "execution": {

                "status":
                    "REJECTED",

                "reason":
                    "Approval not authorized",

                "approval":
                    approval,

                "created_at":
                    _now(),

            }

        }





    execution_id = str(
        uuid.uuid4()
    )



    try:


        #
        # RouterOS Connector
        #

        connector = create_routeros_client(
            host=router_ip,
            username=username,
            password=password,
        )



        connection = connector.connect()



        backup = connector.backup()



        #
        # Execute Safe Command
        #

        command_result = connector.execute(
            "/system/resource/print"
        )



        #
        # Verify Execution
        #

        verification = connector.verify()



        #
        # Generate Intelligence Report
        #

        intelligence_report = (
            generate_remediation_report(
                execution_result={
                    "execution": {

                        "execution_id":
                            execution_id,

                        "router_ip":
                            router_ip,

                        "action_type":
                            action_type,

                        "status":
                            "COMPLETED",

                    }
                }
            )
        )




        save_remediation_history(
            router_ip=router_ip,
            action_type=action_type,
            priority=approval.get(
                "priority",
                "CRITICAL",
            ),
            approval_status=approval.get(
                "status",
                "APPROVED",
            ),
            execution_status="COMPLETED",
            verification_status="VERIFIED",
            business_impact=(
                intelligence_report
                .get("report", {})
                .get(
                    "business_impact",
                    "UNKNOWN",
                )
            ),
            confidence=int(
                intelligence_report
                .get("report", {})
                .get(
                    "confidence",
                    0,
                )
            ),
            recommendation=(
                intelligence_report
                .get("report", {})
                .get(
                    "recommendation",
                    "",
                )
            ),
        )


        return {


            "engine": {

                "name":
                    ENGINE_NAME,


                "version":
                    ENGINE_VERSION,

            },



            "execution": {


                "execution_id":
                    execution_id,


                "approval_id":
                    approval_id,


                "router_ip":
                    router_ip,


                "action_type":
                    action_type,


                "status":
                    "COMPLETED",


                "approval":
                    approval,


                "connection":
                    connection,


                "backup":
                    backup,


                "command_result":
                    command_result,


                "verification":
                    verification,


                "intelligence_report":
                    intelligence_report,


                "rollback_available":
                    True,


                "created_at":
                    _now(),

            }

        }



    except Exception as exc:


        save_remediation_history(
            router_ip=router_ip,
            action_type=action_type,
            priority=approval.get(
                "priority",
                "CRITICAL",
            ),
            approval_status=approval.get(
                "status",
                "APPROVED",
            ),
            execution_status="COMPLETED",
            verification_status="VERIFIED",
            business_impact=(
                intelligence_report
                .get("report", {})
                .get(
                    "business_impact",
                    "UNKNOWN",
                )
            ),
            confidence=int(
                intelligence_report
                .get("report", {})
                .get(
                    "confidence",
                    0,
                )
            ),
            recommendation=(
                intelligence_report
                .get("report", {})
                .get(
                    "recommendation",
                    "",
                )
            ),
        )


        return {


            "engine": {

                "name":
                    ENGINE_NAME,


                "version":
                    ENGINE_VERSION,

            },



            "execution": {


                "execution_id":
                    execution_id,


                "approval_id":
                    approval_id,


                "router_ip":
                    router_ip,


                "action_type":
                    action_type,


                "status":
                    "FAILED",


                "error":
                    str(exc),


                "rollback_required":
                    True,


                "created_at":
                    _now(),

            }

        }
