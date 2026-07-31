from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.decision import (
    DecisionIntelligenceResult,
)
from app.models.device import (
    DeviceSnapshot,
    DeviceStatus,
)
from app.models.traffic import (
    TrafficSeries,
)
from app.services.decision_engine import (
    analyze_decision_intelligence,
)


DOMAIN_INTEGRATION_VERSION = "1.6.1"


def _dictionary(
    value: Any,
) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _list_of_dictionaries(
    value: Any,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    return [
        item
        for item in value
        if isinstance(item, dict)
    ]


def _number(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if numeric_value != numeric_value:
        return None

    return numeric_value


def _extract_interfaces(
    interfaces_snapshot: dict[
        str,
        Any,
    ] | None,
) -> list[dict[str, Any]]:
    snapshot = _dictionary(
        interfaces_snapshot
    )

    return _list_of_dictionaries(
        snapshot.get(
            "interfaces",
            [],
        )
    )


def _extract_traffic_points(
    traffic_snapshot: dict[
        str,
        Any,
    ] | None,
) -> list[dict[str, Any]]:
    snapshot = _dictionary(
        traffic_snapshot
    )

    return _list_of_dictionaries(
        snapshot.get(
            "points",
            [],
        )
    )


def _extract_device_name(
    system_snapshot: dict[
        str,
        Any,
    ] | None,
    router_ip: str,
) -> str:
    snapshot = _dictionary(
        system_snapshot
    )

    return str(
        snapshot.get("identity")
        or snapshot.get("name")
        or snapshot.get(
            "device_name"
        )
        or router_ip
    )


def _extract_cpu_usage(
    system_snapshot: dict[
        str,
        Any,
    ] | None,
) -> float | None:
    snapshot = _dictionary(
        system_snapshot
    )

    for key in (
        "cpu_usage",
        "cpu_percent",
        "cpu_load",
        "cpu-load",
    ):
        value = _number(
            snapshot.get(key)
        )

        if value is not None:
            return value

    return None


def _extract_memory_usage(
    system_snapshot: dict[
        str,
        Any,
    ] | None,
) -> float | None:
    snapshot = _dictionary(
        system_snapshot
    )

    for key in (
        "memory_usage",
        "memory_percent",
    ):
        value = _number(
            snapshot.get(key)
        )

        if value is not None:
            return value

    total_memory = _number(
        snapshot.get(
            "total_memory_bytes"
        )
        or snapshot.get(
            "total-memory"
        )
    )

    free_memory = _number(
        snapshot.get(
            "free_memory_bytes"
        )
        or snapshot.get(
            "free-memory"
        )
    )

    if (
        total_memory is None
        or total_memory <= 0
        or free_memory is None
    ):
        return None

    used_memory = max(
        0.0,
        total_memory - free_memory,
    )

    return round(
        min(
            used_memory
            / total_memory
            * 100.0,
            100.0,
        ),
        2,
    )


def _resolve_device_status(
    *,
    system_available: bool,
    interfaces_available: bool,
) -> DeviceStatus:
    if not system_available:
        return DeviceStatus.OFFLINE

    if not interfaces_available:
        return DeviceStatus.DEGRADED

    return DeviceStatus.ONLINE


def build_device_snapshot(
    *,
    router_ip: str,
    system_snapshot: dict[
        str,
        Any,
    ] | None,
    interfaces_snapshot: dict[
        str,
        Any,
    ] | None,
    system_available: bool | None = None,
    interfaces_available:
        bool | None = None,
) -> DeviceSnapshot:
    """
    Convert RouterOS and interfaces responses into the canonical
    SS4TS DeviceSnapshot model.
    """
    safe_system_snapshot = _dictionary(
        system_snapshot
    )

    safe_interfaces_snapshot = (
        _dictionary(
            interfaces_snapshot
        )
    )

    interfaces = _extract_interfaces(
        safe_interfaces_snapshot
    )

    if system_available is None:
        system_available = bool(
            safe_system_snapshot
        )

    if interfaces_available is None:
        interfaces_available = bool(
            safe_interfaces_snapshot
        )

    status = _resolve_device_status(
        system_available=(
            system_available
        ),
        interfaces_available=(
            interfaces_available
        ),
    )

    merged_device_data = {
        **safe_system_snapshot,

        "router_ip": router_ip,

        "identity":
            _extract_device_name(
                safe_system_snapshot,
                router_ip,
            ),

        "status": status.value,

        "cpu_usage":
            _extract_cpu_usage(
                safe_system_snapshot
            ),

        "memory_usage":
            _extract_memory_usage(
                safe_system_snapshot
            ),

        "metadata": {
            "domain_integration_version":
                DOMAIN_INTEGRATION_VERSION,

            "system_available":
                system_available,

            "interfaces_available":
                interfaces_available,

            "interfaces_summary":
                safe_interfaces_snapshot.get(
                    "summary"
                ),

            "selected_interface":
                safe_interfaces_snapshot.get(
                    "selected_interface"
                ),
        },
    }

    return DeviceSnapshot.from_dict(
        merged_device_data,
        interfaces=interfaces,
        default_ip=router_ip,
    )


def _find_interface_speed(
    *,
    device: DeviceSnapshot,
    interface_name: str | None,
) -> float:
    if not interface_name:
        return 0.0

    interface = next(
        (
            item
            for item in device.interfaces
            if item.name
            == interface_name
        ),
        None,
    )

    if interface is None:
        return 0.0

    return interface.speed_bps


def _resolve_interface_name(
    *,
    requested_interface: str | None,
    traffic_snapshot: dict[
        str,
        Any,
    ] | None,
    interfaces_snapshot: dict[
        str,
        Any,
    ] | None,
    device: DeviceSnapshot,
) -> str | None:
    if requested_interface:
        return requested_interface

    safe_traffic = _dictionary(
        traffic_snapshot
    )

    traffic_interface = (
        safe_traffic.get("interface")
        or safe_traffic.get(
            "interface_name"
        )
    )

    if traffic_interface:
        return str(
            traffic_interface
        )

    safe_interfaces = _dictionary(
        interfaces_snapshot
    )

    selected_interface = (
        safe_interfaces.get(
            "selected_interface"
        )
    )

    if selected_interface:
        return str(
            selected_interface
        )

    if not device.interfaces:
        return None

    busiest_interface = max(
        device.interfaces,
        key=lambda item: (
            item.total_bps
        ),
    )

    return busiest_interface.name


def build_traffic_series(
    *,
    router_ip: str,
    device: DeviceSnapshot,
    traffic_snapshot: dict[
        str,
        Any,
    ] | None,
    interfaces_snapshot: dict[
        str,
        Any,
    ] | None = None,
    selected_interface:
        str | None = None,
    range_minutes: int = 15,
    window_seconds: int = 10,
) -> TrafficSeries:
    """
    Convert the existing traffic-history response into the canonical
    TrafficSeries model.
    """
    safe_traffic_snapshot = (
        _dictionary(
            traffic_snapshot
        )
    )

    interface_name = (
        _resolve_interface_name(
            requested_interface=(
                selected_interface
            ),
            traffic_snapshot=(
                safe_traffic_snapshot
            ),
            interfaces_snapshot=(
                interfaces_snapshot
            ),
            device=device,
        )
    )

    interface_speed = (
        _find_interface_speed(
            device=device,
            interface_name=(
                interface_name
            ),
        )
    )

    traffic_data = {
        **safe_traffic_snapshot,

        "router_ip": router_ip,

        "interface":
            interface_name,

        "range_minutes":
            safe_traffic_snapshot.get(
                "range_minutes",
                range_minutes,
            ),

        "window_seconds":
            safe_traffic_snapshot.get(
                "window_seconds",
                window_seconds,
            ),

        "interface_speed_bps":
            interface_speed,

        "points":
            _extract_traffic_points(
                safe_traffic_snapshot
            ),

        "metadata": {
            "domain_integration_version":
                DOMAIN_INTEGRATION_VERSION,

            "device_identity":
                device.identity,

            "device_status":
                device.status.value,

            "interface_speed_source":
                (
                    "device_snapshot"
                    if interface_speed > 0
                    else "unavailable"
                ),
        },
    }

    return TrafficSeries.from_dict(
        traffic_data,
        default_ip=router_ip,
        interface_speed_bps=(
            interface_speed
        ),
    )


def _build_root_causes_from_signals(
    raw_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build ranked root causes aligned with the Decision Engine signals.

    Alignment rule:
        The first root cause must always reference the current
        top signal whenever a top signal is available.

    This guarantees the explainability chain:

        Top Signal
            -> Primary Root Cause
            -> Primary Recommendation
            -> Primary Decision
    """
    explicit_root_causes = (
        _list_of_dictionaries(
            raw_result.get(
                "root_causes",
                [],
            )
        )
    )

    raw_signals = (
        _list_of_dictionaries(
            raw_result.get(
                "signals",
                [],
            )
        )
    )

    top_signal = raw_result.get(
        "top_signal"
    )

    if not isinstance(
        top_signal,
        dict,
    ):
        top_signal = (
            raw_signals[0]
            if raw_signals
            else None
        )

    top_signal_id = (
        str(
            top_signal.get("id")
            or top_signal.get(
                "signal_id"
            )
            or ""
        )
        if isinstance(
            top_signal,
            dict,
        )
        else ""
    )

    def signal_id(
        signal: dict[str, Any],
    ) -> str:
        return str(
            signal.get("id")
            or signal.get(
                "signal_id"
            )
            or "unknown-signal"
        )

    def confidence_value(
        signal: dict[str, Any],
    ) -> float:
        value = (
            signal.get(
                "confidence"
            )
            if signal.get(
                "confidence"
            )
            is not None
            else signal.get(
                "confidence_percent",
                0,
            )
        )

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    def risk_priority(
        value: Any,
    ) -> int:
        return {
            "critical": 5,
            "high": 4,
            "medium": 3,
            "low": 2,
            "healthy": 1,
            "unknown": 0,
        }.get(
            str(
                value or "unknown"
            ).lower(),
            0,
        )

    def cause_from_signal(
        signal: dict[str, Any],
    ) -> dict[str, Any]:
        current_signal_id = (
            signal_id(signal)
        )

        confidence = (
            confidence_value(
                signal
            )
        )

        return {
            "id": (
                "root-cause-"
                f"{current_signal_id}"
            ),

            "title": (
                signal.get("title")
                or "Probable root cause"
            ),

            "description": (
                signal.get(
                    "description",
                    "",
                )
            ),

            "category":
                "root_cause",

            "risk": (
                signal.get(
                    "risk",
                    "unknown",
                )
            ),

            "confidence":
                confidence,

            "probability_percent":
                confidence,

            "interface_name": (
                signal.get(
                    "interface_name"
                )
            ),

            "device_ip": (
                signal.get(
                    "device_ip"
                )
                or signal.get(
                    "router_ip"
                )
            ),

            "signals": [
                current_signal_id
            ],

            "supporting_signal_ids": [
                current_signal_id
            ],

            "evidence": (
                signal.get(
                    "evidence",
                    {},
                )
            ),

            "alternative_causes": [],

            "recommendation": (
                signal.get(
                    "recommendation"
                )
            ),

            "metadata": {
                "generated_from_signal":
                    True,

                "is_top_signal_cause": (
                    current_signal_id
                    == top_signal_id
                ),
            },
        }

    aligned_causes: list[
        dict[str, Any]
    ] = []

    used_signal_ids: set[str] = set()

    # ---------------------------------------------------------
    # 1. Always align the primary root cause with the top signal.
    # ---------------------------------------------------------

    if isinstance(
        top_signal,
        dict,
    ):
        aligned_causes.append(
            cause_from_signal(
                top_signal
            )
        )

        used_signal_ids.add(
            signal_id(
                top_signal
            )
        )

    # ---------------------------------------------------------
    # 2. Preserve explicit causes that support other signals.
    # ---------------------------------------------------------

    for cause in explicit_root_causes:
        supporting_ids = (
            cause.get(
                "supporting_signal_ids"
            )
            or cause.get(
                "signals"
            )
            or []
        )

        if not isinstance(
            supporting_ids,
            list,
        ):
            supporting_ids = []

        normalized_ids = [
            str(item)
            for item in supporting_ids
            if item
        ]

        if (
            top_signal_id
            and top_signal_id
            in normalized_ids
        ):
            # The generated aligned cause already represents
            # the top signal and must stay first.
            continue

        aligned_causes.append(
            cause
        )

        used_signal_ids.update(
            normalized_ids
        )

    # ---------------------------------------------------------
    # 3. Generate additional causes from relevant signals.
    # ---------------------------------------------------------

    additional_signals = sorted(
        raw_signals,
        key=lambda signal: (
            risk_priority(
                signal.get("risk")
            ),
            float(
                signal.get(
                    "score",
                    0,
                )
                or 0
            ),
            confidence_value(
                signal
            ),
        ),
        reverse=True,
    )

    for signal in additional_signals:
        current_signal_id = (
            signal_id(signal)
        )

        if (
            current_signal_id
            in used_signal_ids
        ):
            continue

        category = str(
            signal.get("category")
            or ""
        ).lower()

        risk = str(
            signal.get("risk")
            or ""
        ).lower()

        is_root_cause_candidate = (
            category
            in {
                "root_cause",
                "correlation",
                "failure",
                "capacity",
                "availability",
                "connectivity",
                "errors",
            }
            or risk
            in {
                "critical",
                "high",
                "medium",
            }
        )

        if not is_root_cause_candidate:
            continue

        aligned_causes.append(
            cause_from_signal(
                signal
            )
        )

        used_signal_ids.add(
            current_signal_id
        )

    return aligned_causes[:5]

def _build_recommendations_from_decisions(
    raw_result: dict[str, Any],
) -> list[dict[str, Any]]:
    explicit_recommendations = (
        _list_of_dictionaries(
            raw_result.get(
                "recommendations",
                [],
            )
        )
    )

    if explicit_recommendations:
        return explicit_recommendations

    raw_decisions = (
        _list_of_dictionaries(
            raw_result.get(
                "decisions",
                [],
            )
        )
    )

    return [
        {
            "id":
                f"recommendation-{item.get('id', index)}",

            "title":
                item.get("title")
                or "Engineering recommendation",

            "action":
                item.get("action")
                or "",

            "type":
                "investigate",

            "priority":
                item.get(
                    "priority",
                    "low",
                ),

            "reason":
                item.get("reason"),

            "expected_impact":
                item.get(
                    "expected_impact"
                ),

            "confidence":
                item.get(
                    "confidence",
                    0,
                ),

            "interface_name":
                item.get(
                    "interface_name"
                ),

            "requires_approval":
                item.get(
                    "requires_approval",
                    True,
                ),
        }
        for index, item
        in enumerate(
            raw_decisions
        )
    ]


def normalize_decision_result(
    *,
    raw_result: dict[str, Any],
    device: DeviceSnapshot,
    traffic: TrafficSeries,
    data_sources: dict[
        str,
        Any,
    ] | None = None,
) -> DecisionIntelligenceResult:
    """
    Convert the legacy decision-engine dictionary into the canonical
    DecisionIntelligenceResult model.
    """
    safe_result = _dictionary(
        raw_result
    )

    normalized_payload = {
        **safe_result,

        "router_ip":
            device.router_ip,

        "device_name":
            device.identity,

        "generated_at":
            safe_result.get(
                "generated_at"
            )
            or datetime.now(
                timezone.utc
            ).isoformat(),

        "root_causes":
            _build_root_causes_from_signals(
                safe_result
            ),

        "recommendations":
            _build_recommendations_from_decisions(
                safe_result
            ),

        "analysis_context": {
            **_dictionary(
                safe_result.get(
                    "analysis_context",
                    {},
                )
            ),

            "domain_integration_version":
                DOMAIN_INTEGRATION_VERSION,

            "device_status":
                device.status.value,

            "device_health_flags":
                device.health_flags,

            "selected_interface":
                traffic.interface_name,

            "traffic_quality":
                traffic.quality.value,

            "traffic_completeness_percent":
                traffic.completeness_percent,

            "traffic_sample_count":
                traffic.sample_count,

            "traffic_health_flags":
                traffic.health_flags,

            "interface_speed_bps":
                traffic.interface_speed_bps,
        },

        "data_sources": (
            data_sources or {}
        ),

        "metadata": {
            **_dictionary(
                safe_result.get(
                    "metadata",
                    {},
                )
            ),

            "domain_models": {
                "device":
                    "DeviceSnapshot",

                "interface":
                    "InterfaceSnapshot",

                "traffic":
                    "TrafficSeries",

                "decision":
                    "DecisionIntelligenceResult",
            },
        },
    }

    return (
        DecisionIntelligenceResult.from_dict(
            normalized_payload
        )
    )


def run_decision_analysis_domain(
    *,
    router_ip: str,
    system_snapshot: dict[
        str,
        Any,
    ] | None,
    interfaces_snapshot: dict[
        str,
        Any,
    ] | None,
    traffic_snapshot: dict[
        str,
        Any,
    ] | None,
    selected_interface:
        str | None = None,
    range_minutes: int = 15,
    window_seconds: int = 10,
    data_sources: dict[
        str,
        Any,
    ] | None = None,
    system_available:
        bool | None = None,
    interfaces_available:
        bool | None = None,
) -> DecisionIntelligenceResult:
    """
    Main integration entry point.

    Raw monitoring snapshots are normalized into domain models before
    being passed to the existing Decision Intelligence Engine.
    """
    device = build_device_snapshot(
        router_ip=router_ip,
        system_snapshot=(
            system_snapshot
        ),
        interfaces_snapshot=(
            interfaces_snapshot
        ),
        system_available=(
            system_available
        ),
        interfaces_available=(
            interfaces_available
        ),
    )

    traffic = build_traffic_series(
        router_ip=router_ip,
        device=device,
        traffic_snapshot=(
            traffic_snapshot
        ),
        interfaces_snapshot=(
            interfaces_snapshot
        ),
        selected_interface=(
            selected_interface
        ),
        range_minutes=(
            range_minutes
        ),
        window_seconds=(
            window_seconds
        ),
    )

    raw_result = (
        analyze_decision_intelligence(
            router_ip=device.router_ip,

            device_name=
                device.identity,

            cpu_usage=
                device.cpu_usage,

            memory_usage=
                device.memory_usage,

            interfaces=[
                interface.to_dict()
                for interface
                in device.interfaces
            ],

            traffic_history=[
                point.to_dict()
                for point
                in traffic.points
            ],

            selected_interface=
                traffic.interface_name,

            sample_seconds=
                traffic.window_seconds,
        )
    )

    return normalize_decision_result(
        raw_result=raw_result,
        device=device,
        traffic=traffic,
        data_sources=data_sources,
    )


def serialize_decision_analysis(
    result: DecisionIntelligenceResult,
) -> dict[str, Any]:
    """
    Serialize a domain result using the JSON structure expected by the
    current REST API and frontend.
    """
    payload = result.to_dict()

    payload[
        "domain_integration"
    ] = {
        "enabled": True,

        "version":
            DOMAIN_INTEGRATION_VERSION,

        "models": [
            "DeviceSnapshot",
            "InterfaceSnapshot",
            "TrafficSeries",
            "DecisionIntelligenceResult",
        ],
    }

    return payload
