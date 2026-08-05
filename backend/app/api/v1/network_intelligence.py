from __future__ import annotations

from ipaddress import IPv4Address

from fastapi import APIRouter, HTTPException, Query

from app.services.network_intelligence import (
    get_network_intelligence,
)


router = APIRouter(
    prefix="/devices",
    tags=["network-intelligence"],
)


def _validate_router_ip(router_ip: str) -> str:
    try:
        return str(IPv4Address(router_ip))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address",
        ) from exc


@router.get(
    "/{router_ip}/network-intelligence"
)
def network_intelligence(
    router_ip: str,
    include_history: bool = Query(
        default=True,
    ),
    history_minutes: int = Query(
        default=15,
        ge=1,
        le=1440,
    ),
    history_window_seconds: int = Query(
        default=10,
        ge=1,
        le=300,
    ),
) -> dict:
    """
    Return unified live network intelligence.

    Includes:
    - RouterOS resource metrics
    - Traffic and traffic history
    - Ping and packet-loss metrics
    - LTE signal metrics
    - Health scoring
    - Findings and recommendations
    """

    validated_ip = _validate_router_ip(
        router_ip
    )

    try:
        return get_network_intelligence(
            router_ip=validated_ip,
            include_history=include_history,
            history_minutes=history_minutes,
            history_window_seconds=(
                history_window_seconds
            ),
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Network intelligence query failed: "
                f"{exc}"
            ),
        ) from exc
