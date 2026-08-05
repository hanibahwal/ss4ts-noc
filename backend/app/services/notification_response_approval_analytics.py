from __future__ import annotations

from pathlib import Path

from datetime import datetime, timezone


from app.services.notification_response_approval import (
    NotificationResponseApprovalStore,
)


from app.services.notification_response_execution_history import (
    NotificationResponseExecutionHistoryStore,
)



class NotificationResponseApprovalAnalyticsService:
    """
    H23.4.5.5.12.22.13.2

    Approval Analytics & Governance Layer

    Responsible for:

    - approval statistics
    - risk distribution
    - action analytics
    - approval performance
    """



    def __init__(
        self,
        database_path: Path,
    ):

        self.approval_store = (
            NotificationResponseApprovalStore(
                database_path
            )
        )


        self.execution_store = (
            NotificationResponseExecutionHistoryStore(
                database_path
            )
        )




    def generate(
        self,
    ) -> dict:


        approvals = (
            self.approval_store.list_history(
                1000
            )
        )


        executions = (
            self.execution_store.list_history(
                1000
            )
        )



        total_requests = len(
            approvals
        )


        pending = 0

        approved = 0

        rejected = 0



        risk_distribution = {

            "high": 0,

            "medium": 0,

            "low": 0,

        }



        actions = {}



        approval_times = []



        for item in approvals:


            data = item.to_dict()



            status = (
                data.get(
                    "status"
                )
            )



            if status == "pending":

                pending += 1



            elif status == "approved":

                approved += 1



            elif status == "rejected":

                rejected += 1



            risk = (
                data.get(
                    "risk_level",
                    "low"
                )
            )


            if risk in risk_distribution:

                risk_distribution[risk] += 1



            action_type = (
                data.get(
                    "action_type",
                    "unknown"
                )
            )



            if action_type not in actions:


                actions[action_type] = {

                    "total": 0,

                    "approved": 0,

                    "rejected": 0,

                }



            actions[action_type]["total"] += 1



            if status == "approved":

                actions[action_type]["approved"] += 1



            if status == "rejected":

                actions[action_type]["rejected"] += 1




        approval_rate = 0



        if total_requests:

            approval_rate = round(
                (
                    approved /
                    total_requests
                )
                *
                100,

                2,
            )



        return {


            "summary": {


                "total_requests":
                    total_requests,


                "pending":
                    pending,


                "approved":
                    approved,


                "rejected":
                    rejected,


                "approval_rate":
                    approval_rate,


            },



            "performance": {


                "average_approval_time_seconds":
                    self._average_time(
                        approval_times
                    ),


            },



            "risk_distribution":
                risk_distribution,



            "actions":
                list(
                    actions.values()
                ),


            "generated_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

        }




    def _average_time(
        self,
        values: list[int],
    ) -> int:


        if not values:

            return 0


        return int(
            sum(values)
            /
            len(values)
        )
