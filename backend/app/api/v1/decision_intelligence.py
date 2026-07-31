from __future__ import annotations

from ipaddress import IPv4Address
from typing import Any

import httpx
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.services.domain_integration import (
    run_decision_analysis_domain,
    serialize_decision_analysis,
)
from app.services.routeros import (
    get_system_snapshot,
)
from app.services.traffic import (
    get_interface_history,
    get_interfaces_snapshot,
)


router = APIRouter(
    prefix="/devices",
    tags=["decision-intelligence"],
)


def _validate_router_ip(
    router_ip: str,
) -> str:
    """
    Validate and normalize the supplied IPv4 address.
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


def _source_status(
    *,
    available: bool,
    error: str | None = None,
    item_count: int | None = None,
) -> dict[str, Any]:
    """
    Create a consistent status object for every monitoring source.
    """
    result: dict[str, Any] = {
        "available": available,
        "status": (
            "available"
            if available
            else "unavailable"
        ),
        "error": error,
    }

    if item_count is not None:
        result["item_count"] = max(
            0,
            int(item_count),
        )

    return result


def _extract_interfaces(
    snapshot: dict[
        str,
        Any,
    ] | None,
) -> list[dict[str, Any]]:
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


def _extract_history_points(
    snapshot: dict[
        str,
        Any,
    ] | None,
) -> list[dict[str, Any]]:
    if not isinstance(
        snapshot,
        dict,
    ):
        return []

    points = snapshot.get(
        "points",
        [],
    )

    if not isinstance(
        points,
        list,
    ):
        return []

    return [
        item
        for item in points
        if isinstance(item, dict)
    ]


def _resolve_selected_interface(
    *,
    requested_interface: str | None,
    interfaces_snapshot: dict[
        str,
        Any,
    ] | None,
) -> str | None:
    """
    Resolve the interface requested by the client or selected by the
    interfaces service.
    """
    if requested_interface:
        return requested_interface

    if not isinstance(
        interfaces_snapshot,
        dict,
    ):
        return None

    selected_interface = (
        interfaces_snapshot.get(
            "selected_interface"
        )
    )

    if selected_interface:
        return str(
            selected_interface
        )

    interfaces = _extract_interfaces(
        interfaces_snapshot
    )

    if not interfaces:
        return None

    busiest_interface = max(
        interfaces,
        key=lambda item: float(
            item.get("total_bps")
            or (
                float(
                    item.get("rx_bps")
                    or 0
                )
                + float(
                    item.get("tx_bps")
                    or 0
                )
            )
        ),
    )

    interface_name = (
        busiest_interface.get(
            "if_descr"
        )
        or busiest_interface.get(
            "name"
        )
    )

    return (
        str(interface_name)
        if interface_name
        else None
    )


def _routeros_error_message(
    exc: Exception,
) -> str:
    """
    Convert RouterOS/httpx exceptions into readable data-source errors.
    """
    if isinstance(
        exc,
        httpx.ConnectError,
    ):
        return (
            "Cannot connect to "
            "RouterOS REST API"
        )

    if isinstance(
        exc,
        httpx.TimeoutException,
    ):
        return (
            "RouterOS REST API "
            "request timed out"
        )

    if isinstance(
        exc,
        httpx.HTTPStatusError,
    ):
        return (
            "RouterOS REST API "
            "returned HTTP "
            f"{exc.response.status_code}"
        )

    return str(exc)


@router.get(
    "/{router_ip}/decision-intelligence",
    summary=(
        "Analyze device decision intelligence"
    ),
    description=(
        "Collect RouterOS, interface and traffic-history data, "
        "normalize them through SS4TS domain models, and return "
        "explainable engineering signals, probable root causes "
        "and recommended decisions."
    ),
)
def device_decision_intelligence(
    router_ip: str,

    interface: str | None = Query(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Interface to analyze. When omitted, SS4TS selects "
            "the current or busiest interface."
        ),
    ),

    minutes: int = Query(
        default=15,
        ge=1,
        le=1440,
        description=(
            "Historical analysis range in minutes."
        ),
    ),

    window: int = Query(
        default=10,
        ge=1,
        le=300,
        description=(
            "Traffic aggregation window in seconds."
        ),
    ),
) -> dict[str, Any]:
    """
    Return domain-integrated Decision Intelligence analysis.

    The endpoint intentionally does not implement business logic.
    Its responsibilities are limited to:

    1. Input validation.
    2. Monitoring-source collection.
    3. Source availability reporting.
    4. Domain integration invocation.
    5. JSON serialization.
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

    traffic_snapshot: dict[
        str,
        Any,
    ] | None = None

    system_error: str | None = None
    interfaces_error: str | None = None
    traffic_error: str | None = None

    # ---------------------------------------------------------
    # 1. RouterOS system snapshot
    # ---------------------------------------------------------

    try:
        system_snapshot = (
            get_system_snapshot(
                validated_ip
            )
        )

    except (
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.HTTPStatusError,
        RuntimeError,
    ) as exc:
        system_error = (
            _routeros_error_message(
                exc
            )
        )

    except Exception as exc:
        system_error = (
            "RouterOS snapshot failed: "
            f"{exc}"
        )

    # ---------------------------------------------------------
    # 2. Interfaces snapshot
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

    selected_interface = (
        _resolve_selected_interface(
            requested_interface=interface,
            interfaces_snapshot=(
                interfaces_snapshot
            ),
        )
    )

    # ---------------------------------------------------------
    # 3. Traffic history
    # ---------------------------------------------------------

    if selected_interface:
        try:
            traffic_snapshot = (
                get_interface_history(
                    router_ip=validated_ip,
                    interface_name=(
                        selected_interface
                    ),
                    range_minutes=minutes,
                    window_seconds=window,
                )
            )

        except Exception as exc:
            traffic_error = (
                "Traffic history failed: "
                f"{exc}"
            )

    else:
        traffic_error = (
            "No interface was available "
            "for traffic-history analysis"
        )

    history_points = (
        _extract_history_points(
            traffic_snapshot
        )
    )

    system_available = isinstance(
        system_snapshot,
        dict,
    )

    interfaces_available = isinstance(
        interfaces_snapshot,
        dict,
    )

    traffic_available = isinstance(
        traffic_snapshot,
        dict,
    )

    data_sources = {
        "routeros": _source_status(
            available=system_available,
            error=system_error,
        ),

        "interfaces": _source_status(
            available=interfaces_available,
            error=interfaces_error,
            item_count=len(
                interfaces
            ),
        ),

        "traffic_history": (
            _source_status(
                available=traffic_available,
                error=traffic_error,
                item_count=len(
                    history_points
                ),
            )
        ),
    }

    # ---------------------------------------------------------
    # 4. Domain integration and decision analysis
    # ---------------------------------------------------------

    try:
        domain_result = (
            run_decision_analysis_domain(
                router_ip=validated_ip,

                system_snapshot=(
                    system_snapshot
                ),

                interfaces_snapshot=(
                    interfaces_snapshot
                ),

                traffic_snapshot=(
                    traffic_snapshot
                ),

                selected_interface=(
                    selected_interface
                ),

                range_minutes=minutes,

                window_seconds=window,

                data_sources=(
                    data_sources
                ),

                system_available=(
                    system_available
                ),

                interfaces_available=(
                    interfaces_available
                ),
            )
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Decision Intelligence "
                "domain analysis failed: "
                f"{exc}"
            ),
        ) from exc

    # ---------------------------------------------------------
    # 5. API-compatible serialization
    # ---------------------------------------------------------

    payload = (
        serialize_decision_analysis(
            domain_result
        )
    )

    payload["request_context"] = {
        "router_ip": validated_ip,

        "selected_interface":
            selected_interface,

        "minutes": minutes,

        "window_seconds":
            window,

        "interfaces_received":
            len(interfaces),

        "history_points_received":
            len(history_points),

        "partial_data": not (
            system_available
            and interfaces_available
            and traffic_available
        ),

        "domain_integration_enabled":
            True,
    }

    return payload
