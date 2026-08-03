from __future__ import annotations

from pathlib import Path


from app.services.notification_audit_decision_runtime import (
    NotificationDecisionRuntime,
)

from app.services.notification_response_planner import (
    NotificationResponsePlanner,
)

from app.services.notification_execution_guard import (
    NotificationExecutionGuard,
)

from app.services.notification_response_execution_history import (
    NotificationResponseExecutionHistoryStore,
)




class NotificationResponseExecutionRuntime:



    def __init__(
        self,
        database_path: Path,
    ):


        self.decision_runtime = (
            NotificationDecisionRuntime(
                database_path
            )
        )


        self.planner = (
            NotificationResponsePlanner()
        )


        self.guard = (
            NotificationExecutionGuard()
        )


        self.history_store = (
            NotificationResponseExecutionHistoryStore(
                database_path
            )
        )




    def execute(self):


        decision_history = (
            self.decision_runtime.execute()
        )


        class Decision:

            risk_level = (
                decision_history.risk_level
            )



        actions = (
            self.planner.build_plan(
                Decision()
            )
        )


        results = []



        for action in actions:


            guard_result = (
                self.guard.check(
                    action
                )
            )



            executed = (
                guard_result.allowed
            )


            result_text = (
                "Executed successfully"
                if executed
                else
                "Waiting for approval"
            )



            history = (
                self.history_store.create(

                    action_id=
                        action.action_id,

                    action_type=
                        action.action_type.value,

                    guard_status=
                        guard_result.status.value,

                    approved=
                        not guard_result.requires_approval,

                    executed=
                        executed,

                    result=
                        result_text,

                )
            )



            results.append({

                "action":
                    action.to_dict(),

                "guard":
                    guard_result.to_dict(),

                "execution":
                    history.to_dict(),

            })



        return {

            "decision":
                decision_history.to_dict(),

            "actions":
                results,

        }
