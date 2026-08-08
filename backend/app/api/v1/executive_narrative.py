from __future__ import annotations

from ipaddress import IPv4Address

from fastapi import APIRouter, HTTPException, Query

from app.services.executive_narrative import (
    build_executive_narrative,
)

from app.services.network_intelligence import (
    get_network_intelligence,
)


router = APIRouter(
    prefix="/devices",
    tags=["executive-narrative"],
)


def _validate_router_ip(
    router_ip: str,
) -> str:

    try:
        return str(
            IPv4Address(router_ip)
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address",
        ) from exc



@router.get(
    "/{router_ip}/executive-narrative"
)
def executive_narrative(
    router_ip: str,

    include_history: bool = Query(
        default=True,
        description="Include historical metrics",
    ),

    history_minutes: int = Query(
        default=15,
        ge=1,
        le=1440,
        description="History window in minutes",
    ),

    history_window_seconds: int = Query(
        default=10,
        ge=1,
        le=300,
        description="Aggregation window seconds",
    ),

) -> dict:
    """
    Executive AI Narrative API

    Generates Arabic executive explanation
    from live Network Intelligence.
    """

    validated_ip = _validate_router_ip(
        router_ip
    )


    try:

        intelligence = (
            get_network_intelligence(
                router_ip=validated_ip,

                include_history=include_history,

                history_minutes=history_minutes,

                history_window_seconds=(
                    history_window_seconds
                ),
            )
        )


        narrative = (
            build_executive_narrative(
                intelligence
            )
        )


        return {

            "router_ip": validated_ip,

            # Expose narrative fields at API root
            # for backward compatibility
            **narrative,

            # Keep complete object
            # for new consumers
            "executive_narrative": narrative,

            "source": "SS4TS-NOC AI Intelligence",

        }


    except HTTPException:

        raise


    except Exception as exc:

        raise HTTPException(

            status_code=503,

            detail=(

                "Executive narrative query "
                f"failed: {exc}"

            ),

        ) from exc
