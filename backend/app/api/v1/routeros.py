from ipaddress import IPv4Address

import httpx
from fastapi import APIRouter, HTTPException

from app.services.routeros import get_system_snapshot


router = APIRouter(
    prefix="/devices",
    tags=["routeros"],
)


@router.get("/{router_ip}/routeros")
def routeros_snapshot(router_ip: str) -> dict:
    try:
        validated_ip = str(IPv4Address(router_ip))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address",
        ) from exc

    try:
        return get_system_snapshot(validated_ip)

    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to RouterOS REST API",
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "RouterOS REST API returned "
                f"HTTP {exc.response.status_code}"
            ),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
