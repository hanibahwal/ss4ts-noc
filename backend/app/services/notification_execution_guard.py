from __future__ import annotations

from datetime import datetime, timezone


from app.models.notification_execution_guard import (
    NotificationExecutionGuardResult,
    ExecutionGuardStatus,
)

from app.models.notification_response_action import (
    NotificationResponseActionType,
)




class NotificationExecutionGuard:



    def check(
        self,
        action,
    ) -> NotificationExecutionGuardResult:



        status = (
            ExecutionGuardStatus.ALLOWED
        )

        allowed = True

        requires_approval = False

        reason = (
            "Action allowed by execution policy"
        )



        sensitive_actions = [

            NotificationResponseActionType.BLOCK_IDENTITY,

            NotificationResponseActionType.DISABLE_TOKEN,

            NotificationResponseActionType.RESTART_SERVICE,

            NotificationResponseActionType.QUARANTINE_DEVICE,

        ]



        if action.action_type in sensitive_actions:


            status = (
                ExecutionGuardStatus.APPROVAL_REQUIRED
            )

            allowed = False

            requires_approval = True

            reason = (
                "Sensitive autonomous action requires administrator approval"
            )



        return NotificationExecutionGuardResult(

            action_id=action.action_id,

            status=status,

            allowed=allowed,

            requires_approval=requires_approval,

            reason=reason,

            checked_at=datetime.now(
                timezone.utc
            ),

        )
