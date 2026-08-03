from __future__ import annotations

from pathlib import Path


from app.models.notification_response_approval_binding import (
    ApprovalExecutionStatus,
)


from app.services.notification_response_approval_binding import (
    NotificationResponseApprovalBindingStore,
)


from app.services.notification_response_execution_runtime import (
    NotificationResponseExecutionRuntime,
)




class NotificationResponseApprovalRuntime:



    def __init__(
        self,
        database_path: Path,
    ):

        self.binding_store = (
            NotificationResponseApprovalBindingStore(
                database_path
            )
        )


        self.execution_runtime = (
            NotificationResponseExecutionRuntime(
                database_path
            )
        )



    def approve_and_execute(
        self,
        approval_id: str,
        action_id: str,
        approved_by: str,
    ):


        binding = (
            self.binding_store.create(
                approval_id,
                action_id,
            )
        )



        execution_result = (
            self.execution_runtime.execute()
        )



        execution_id = None



        if execution_result.get("actions"):

            first_action = (
                execution_result["actions"][0]
            )


            if first_action.get("execution"):

                execution_id = (
                    first_action["execution"]["execution_id"]
                )



        if execution_id:


            self.binding_store.update_execution(

                binding.binding_id,

                execution_id,

                ApprovalExecutionStatus.COMPLETED,

            )



        return {


            "approval_id":

                approval_id,


            "approved_by":

                approved_by,


            "binding":

                self.binding_store
                .latest()
                .to_dict(),



            "execution":

                execution_result,


        }
