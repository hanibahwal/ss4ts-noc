from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


from app.models.notification_response_action import (
    NotificationResponseAction,
    NotificationResponseActionType,
)



class NotificationResponsePlanner:



    def build_plan(
        self,
        decision,
    ) -> list[NotificationResponseAction]:


        actions = []



        risk = decision.risk_level



        if risk == "critical":


            actions.append(

                NotificationResponseAction(

                    action_id=str(uuid4()),

                    action_type=
                    NotificationResponseActionType.BLOCK_IDENTITY,

                    risk_level=risk,

                    requires_approval=True,

                    reversible=True,

                    description=
                    "Block suspicious notification identity",

                    created_at=
                    datetime.now(timezone.utc),

                )

            )



            actions.append(

                NotificationResponseAction(

                    action_id=str(uuid4()),

                    action_type=
                    NotificationResponseActionType.CREATE_INCIDENT,

                    risk_level=risk,

                    requires_approval=False,

                    reversible=False,

                    description=
                    "Create security incident",

                    created_at=
                    datetime.now(timezone.utc),

                )

            )



        elif risk == "high":


            actions.append(

                NotificationResponseAction(

                    action_id=str(uuid4()),

                    action_type=
                    NotificationResponseActionType.SEND_ALERT,

                    risk_level=risk,

                    requires_approval=False,

                    reversible=True,

                    description=
                    "Send administrator alert",

                    created_at=
                    datetime.now(timezone.utc),

                )

            )



        else:


            actions.append(

                NotificationResponseAction(

                    action_id=str(uuid4()),

                    action_type=
                    NotificationResponseActionType.CONTINUE_MONITORING,

                    risk_level=risk,

                    requires_approval=False,

                    reversible=True,

                    description=
                    "Continue AI monitoring",

                    created_at=
                    datetime.now(timezone.utc),

                )

            )



        return actions
