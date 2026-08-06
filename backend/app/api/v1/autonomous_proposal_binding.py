from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    HTTPException,
)

from app.models.autonomous_operation_proposal import (
    AutonomousOperationProposal,
)
from app.models.decision_action import (
    DecisionAction,
)
from app.models.execution_plan import (
    ExecutionPlan,
)
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBinding,
)


router = APIRouter(
    prefix="/autonomous-proposals",
    tags=["Autonomous Proposals"],
)


@router.post(
    "/validate-binding",
    summary=(
        "Validate autonomous proposal binding"
    ),
)
async def validate_autonomous_proposal_binding(
    proposal: Annotated[
        AutonomousOperationProposal,
        Body(),
    ],
    action: Annotated[
        DecisionAction,
        Body(),
    ],
    plan: Annotated[
        ExecutionPlan,
        Body(),
    ],
) -> dict:
    """
    Validate the relationship between an autonomous
    proposal, decision action, and execution plan.

    This endpoint performs validation only.

    It never:
    - authorizes execution;
    - starts a simulation;
    - performs network I/O;
    - executes device commands.
    """

    try:
        result = (
            AutonomousProposalBinding()
            .validate(
                proposal=proposal,
                action=action,
                plan=plan,
            )
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    payload = result.to_dict()

    # Defense in depth:
    # The API must never expose execution authority.
    payload["can_execute"] = False

    payload.setdefault(
        "safety",
        {},
    )

    payload["safety"].update(
        {
            "binding_validation_only": True,
            "execution_authority": False,
            "authorization_created": False,
            "simulation_started": False,
            "network_io_performed": False,
            "device_command_executed": False,
            "controlled_execution_required": True,
        }
    )

    return payload
