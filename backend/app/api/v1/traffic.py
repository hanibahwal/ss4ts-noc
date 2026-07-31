from ipaddress import IPv4Address

from fastapi import APIRouter, HTTPException, Query

from app.services.traffic import (
    get_interface_history,
    get_interface_rates,
    get_interfaces_snapshot,
)


router = APIRouter(
    prefix="/devices",
    tags=["traffic"],
)


def _validate_router_ip(router_ip: str) -> str:
    try:
        return str(IPv4Address(router_ip))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address",
        ) from exc


@router.get("/{router_ip}/traffic")
def device_traffic(
    router_ip: str,
) -> dict:
    validated_ip = _validate_router_ip(
        router_ip,
    )

    try:
        return get_interface_rates(
            validated_ip,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Traffic query failed: "
                f"{exc}"
            ),
        ) from exc


@router.get("/{router_ip}/traffic/history")
def device_traffic_history(
    router_ip: str,
    interface: str | None = Query(
        default=None,
        min_length=1,
        max_length=128,
    ),
    minutes: int = Query(
        default=15,
        ge=1,
        le=1440,
    ),
    window: int = Query(
        default=10,
        ge=1,
        le=300,
    ),
) -> dict:
    validated_ip = _validate_router_ip(
        router_ip,
    )

    try:
        return get_interface_history(
            router_ip=validated_ip,
            interface_name=interface,
            range_minutes=minutes,
            window_seconds=window,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Traffic history query failed: "
                f"{exc}"
            ),
        ) from exc


@router.get("/{router_ip}/interfaces")
def device_interfaces(
    router_ip: str,
    minutes: int = Query(
        default=15,
        ge=1,
        le=1440,
    ),
) -> dict:
    validated_ip = _validate_router_ip(
        router_ip,
    )

    try:
        return get_interfaces_snapshot(
            router_ip=validated_ip,
            range_minutes=minutes,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Interfaces query failed: "
                f"{exc}"
            ),
        ) from exc
