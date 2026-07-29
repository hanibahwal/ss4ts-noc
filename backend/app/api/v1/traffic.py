from ipaddress import IPv4Address

from fastapi import APIRouter, HTTPException

from app.services.traffic import get_interface_rates


router = APIRouter(
    prefix="/devices",
    tags=["traffic"],
)


@router.get("/{router_ip}/traffic")
def device_traffic(router_ip: str) -> dict:
    try:
        validated_ip = str(IPv4Address(router_ip))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address",
        ) from exc

    try:
        return get_interface_rates(validated_ip)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Traffic query failed: {exc}",
        ) from exc
