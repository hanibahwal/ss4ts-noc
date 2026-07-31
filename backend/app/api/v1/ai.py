from __future__ import annotations

from ipaddress import IPv4Address
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.services.ai_engine import analyze_device
from app.services.routeros import get_system_snapshot
from app.services.traffic import get_interfaces_snapshot


router = APIRouter(
    prefix="/devices",
    tags=["ai-network-engine"],
)


def _validate_router_ip(
    router_ip: str,
) -> str:
    """
    Validate and normalize the router IPv4 address.
    """
    try:
        return str(
            IPv4Address(router_ip)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address",
        ) from exc


def _extract_interfaces(
    snapshot: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Safely extract the interfaces list from the
    Enterprise Interfaces API response.
    """
    if not isinstance(
        snapshot,
        dict,
    ):
        return []

    interfaces = snapshot.get(
        "interfaces",
        [],
    )

    if not isinstance(
        interfaces,
        list,
    ):
        return []

    return [
        item
        for item in interfaces
        if isinstance(item, dict)
    ]


def _extract_device_name(
    system_snapshot: dict[str, Any] | None,
    router_ip: str,
) -> str:
    """
    Resolve the most useful device name available
    from the RouterOS system snapshot.
    """
    if not isinstance(
        system_snapshot,
        dict,
    ):
        return router_ip

    return str(
        system_snapshot.get("identity")
        or system_snapshot.get("name")
        or system_snapshot.get(
            "device_name"
        )
        or router_ip
    )


def _extract_number(
    source: dict[str, Any] | None,
    *keys: str,
) -> float | None:
    """
    Return the first valid numeric value from
    the supplied dictionary keys.
    """
    if not isinstance(
        source,
        dict,
    ):
        return None

    for key in keys:
        value = source.get(key)

        if value is None:
            continue

        try:
            numeric_value = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            numeric_value
            != numeric_value
        ):
            continue

        return numeric_value

    return None


def _source_status(
    *,
    available: bool,
    error: str | None = None,
) -> dict[str, Any]:
    """
    Build a consistent data-source status object.
    """
    return {
        "available": available,
        "status": (
            "online"
            if available
            else "unavailable"
        ),
        "error": error,
    }


@router.get("/{router_ip}/ai")
def device_ai_analysis(
    router_ip: str,
    minutes: int = Query(
        default=15,
        ge=1,
        le=1440,
        description=(
            "Time range used for the "
            "interfaces snapshot."
        ),
    ),
) -> dict[str, Any]:
    """
    Analyze one monitored network device using the
    SS4TS Explainable AI Network Engine.

    The endpoint combines:

    - RouterOS system information.
    - CPU and memory utilization.
    - Interface operational states.
    - Interface errors.
    - Interface utilization.
    - Explainable root causes.
    - Risk level.
    - Actionable recommendations.
    """
    validated_ip = _validate_router_ip(
        router_ip
    )

    system_snapshot: dict[
        str,
        Any,
    ] | None = None

    interfaces_snapshot: dict[
        str,
        Any,
    ] | None = None

    system_error: str | None = None
    interfaces_error: str | None = None

    # ---------------------------------------------------------
    # RouterOS system snapshot
    # ---------------------------------------------------------

    try:
        system_snapshot = (
            get_system_snapshot(
                validated_ip
            )
        )

    except httpx.ConnectError:
        system_error = (
            "Cannot connect to "
            "RouterOS REST API"
        )

    except httpx.TimeoutException:
        system_error = (
            "RouterOS REST API "
            "request timed out"
        )

    except httpx.HTTPStatusError as exc:
        system_error = (
            "RouterOS REST API "
            "returned HTTP "
            f"{exc.response.status_code}"
        )

    except RuntimeError as exc:
        system_error = str(exc)

    except Exception as exc:
        system_error = (
            "RouterOS snapshot failed: "
            f"{exc}"
        )

    # ---------------------------------------------------------
    # Interfaces snapshot
    # ---------------------------------------------------------

    try:
        interfaces_snapshot = (
            get_interfaces_snapshot(
                router_ip=validated_ip,
                range_minutes=minutes,
            )
        )

    except Exception as exc:
        interfaces_error = (
            "Interfaces snapshot failed: "
            f"{exc}"
        )

    interfaces = _extract_interfaces(
        interfaces_snapshot
    )

    system_available = isinstance(
        system_snapshot,
        dict,
    )

    interfaces_available = (
        isinstance(
            interfaces_snapshot,
            dict,
        )
    )

    # A successful RouterOS snapshot is currently the
    # strongest indicator that the device is online.
    is_online = system_available

    cpu_usage = _extract_number(
        system_snapshot,
        "cpu_usage",
        "cpu_percent",
        "cpu_load",
        "cpu",
    )

    memory_usage = _extract_number(
        system_snapshot,
        "memory_usage",
        "memory_percent",
        "memory",
    )

    device_name = (
        _extract_device_name(
            system_snapshot,
            validated_ip,
        )
    )

    try:
        analysis = analyze_device(
            router_ip=validated_ip,
            device_name=device_name,
            is_online=is_online,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            interfaces=interfaces,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "AI analysis failed: "
                f"{exc}"
            ),
        ) from exc

    # Add transparent information about the input data
    # so the UI can explain whether the analysis is based
    # on complete or partially available monitoring data.
    analysis["data_sources"] = {
        "routeros": _source_status(
            available=system_available,
            error=system_error,
        ),
        "interfaces": _source_status(
            available=(
                interfaces_available
            ),
            error=interfaces_error,
        ),
    }

    analysis["analysis_context"] = {
        "router_ip": validated_ip,
        "device_name": device_name,
        "range_minutes": minutes,
        "is_online": is_online,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "interfaces_received": len(
            interfaces
        ),
        "partial_data": not (
            system_available
            and interfaces_available
        ),
    }

    analysis["source_snapshots"] = {
        "routeros": {
            "identity": (
                system_snapshot.get(
                    "identity"
                )
                if system_available
                else None
            ),
            "board_name": (
                system_snapshot.get(
                    "board_name"
                )
                if system_available
                else None
            ),
            "version": (
                system_snapshot.get(
                    "version"
                )
                if system_available
                else None
            ),
            "cpu_usage": cpu_usage,
            "memory_usage":
                memory_usage,
            "uptime": (
                system_snapshot.get(
                    "uptime"
                )
                if system_available
                else None
            ),
        },
        "interfaces": {
            "summary": (
                interfaces_snapshot.get(
                    "summary"
                )
                if interfaces_available
                else None
            ),
            "selected_interface": (
                interfaces_snapshot.get(
                    "selected_interface"
                )
                if interfaces_available
                else None
            ),
            "total": len(
                interfaces
            ),
        },
    }

    return analysis
