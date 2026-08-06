from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    HTTPException,
)

from app.services.autonomous_authorization_request_audit import (
    AutonomousAuthorizationRequestAuditReport,
)
from app.services.autonomous_authorization_request_store import (
    AutonomousAuthorizationRequestRecord,
)
from app.services.autonomous_controlled_authorization_bridge import (
    AutonomousControlledAuthorizationBridgeError,
    create_autonomous_authorization_intent,
)


router = APIRouter(
    prefix="/autonomous-authorizations",
    tags=["Autonomous Authorizations"],
)


@router.post(
    "/create-intent",
    summary=(
        "Create a non-executable autonomous "
        "authorization intent"
    ),
)
async def create_controlled_authorization_intent(
    request_record: Annotated[
        AutonomousAuthorizationRequestRecord,
        Body(),
    ],
    request_audit: Annotated[
        AutonomousAuthorizationRequestAuditReport,
        Body(),
    ],
    authorization_intent_id: Annotated[
        str | None,
        Body(),
    ] = None,
    created_at: Annotated[
        datetime | None,
        Body(),
    ] = None,
) -> dict:
    """
    Convert one verified authorization request record
    into a non-executable authorization intent.

    This endpoint never:
    - creates ExecutionAuthorization;
    - approves authorization;
    - creates tokens or approval claims;
    - acquires execution leases;
    - starts simulations;
    - accesses networks or devices;
    - generates or executes commands.
    """

    try:
        intent = (
            create_autonomous_authorization_intent(
                request_record=request_record,
                request_audit=request_audit,
                authorization_intent_id=(
                    authorization_intent_id
                ),
                created_at=created_at,
            )
        )

    except (
        TypeError,
        ValueError,
        AutonomousControlledAuthorizationBridgeError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    payload = intent.to_dict()

    # Defense in depth:
    # This API can only expose a non-executable intent.
    payload["execution_authorization_created"] = False
    payload["authorization_approved"] = False
    payload["authorization_token_created"] = False
    payload["approval_claim_created"] = False
    payload["execution_lease_created"] = False
    payload["execution_allowed"] = False
    payload["can_execute"] = False

    payload.setdefault(
        "safety",
        {},
    )

    payload["safety"].update(
        {
            "authorization_intent_only": True,
            "request_store_read_only": True,
            "execution_authorization_created": False,
            "execution_authorization_stored": False,
            "authorization_approved": False,
            "authorization_token_created": False,
            "approval_claim_created": False,
            "execution_lease_created": False,
            "execution_allowed": False,
            "execution_approved": False,
            "simulation_started": False,
            "network_io_performed": False,
            "device_access_performed": False,
            "command_generated": False,
            "device_command_executed": False,
        }
    )

    return payload
