from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ENGINE_NAME = "SS4TS AI Prediction Engine"
ENGINE_VERSION = "1.0.0-rule-based"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _risk_level(score: float) -> str:
    if score >= 80:
        return "critical"

    if score >= 60:
        return "high"

    if score >= 35:
        return "medium"

    return "low"


def _create_event(
    *,
    code: str,
    title: str,
    severity: str,
    confidence: float,
    message: str,
    recommendation: str,
    metric: str,
    value: Any,
) -> dict[str, Any]:

    return {
        "code": code,
        "title": title,
        "severity": severity,
        "confidence_percent": round(
            confidence,
            2,
        ),
        "message": message,
        "recommendation": recommendation,
        "metric": metric,
        "value": value,
        "created_at": _utc_now(),
    }


def predict_cpu_risk(
    device: dict[str, Any],
) -> dict[str, Any] | None:

    cpu = _safe_float(
        device.get(
            "cpu_usage_percent"
        )
    )

    if cpu >= 90:

        return _create_event(
            code="CPU_SATURATION",
            title="High CPU utilization predicted",
            severity="critical",
            confidence=92,
            message=(
                f"CPU usage is {cpu}% "
                "and may cause service degradation."
            ),
            recommendation=(
                "Check running processes, "
                "firewall rules and traffic load."
            ),
            metric="cpu_usage_percent",
            value=cpu,
        )


    if cpu >= 75:

        return _create_event(
            code="CPU_PRESSURE",
            title="CPU pressure increasing",
            severity="warning",
            confidence=75,
            message=(
                f"CPU usage reached {cpu}%."
            ),
            recommendation=(
                "Monitor CPU trend and "
                "prepare optimization."
            ),
            metric="cpu_usage_percent",
            value=cpu,
        )


    return None


def predict_lte_risk(
    lte: dict[str, Any],
) -> dict[str, Any] | None:

    if not lte or lte.get("available") is not True:
        return None


    rsrp = _safe_float(
        lte.get("rsrp_dbm")
    )

    rsrq = _safe_float(
        lte.get("rsrq_db")
    )

    sinr = _safe_float(
        lte.get("sinr_db")
    )


    if rsrq <= -14 or sinr < 5:

        return _create_event(
            code="LTE_DEGRADATION",
            title="LTE quality degradation predicted",
            severity="high",
            confidence=85,
            message=(
                "LTE signal quality is degrading."
            ),
            recommendation=(
                "Check interference, "
                "sector congestion and antenna position."
            ),
            metric="lte_signal_quality",
            value={
                "rsrp": rsrp,
                "rsrq": rsrq,
                "sinr": sinr,
            },
        )


    return None



def predict_traffic_risk(
    traffic: dict[str, Any],
) -> dict[str, Any] | None:


    total_bps = _safe_float(
        traffic.get(
            "total_bps"
        )
    )


    mbps = total_bps / 1_000_000


    if mbps >= 90:

        return _create_event(
            code="TRAFFIC_CONGESTION",
            title="Traffic congestion risk",
            severity="high",
            confidence=80,
            message=(
                f"Traffic load is {round(mbps,2)} Mbps."
            ),
            recommendation=(
                "Check bandwidth usage "
                "and QoS policies."
            ),
            metric="traffic_mbps",
            value=round(
                mbps,
                2,
            ),
        )


    return None



def predict_link_risk(
    ping: dict[str, Any],
) -> dict[str, Any] | None:


    latency = _safe_float(
        ping.get(
            "latency_ms"
        )
    )

    loss = _safe_float(
        ping.get(
            "packet_loss_percent"
        )
    )


    if loss >= 5 or latency >= 200:

        return _create_event(
            code="LINK_INSTABILITY",
            title="Network link instability",
            severity="critical",
            confidence=88,
            message=(
                "Latency or packet loss indicates "
                "possible link failure."
            ),
            recommendation=(
                "Check WAN link, routing "
                "and ISP availability."
            ),
            metric="link_quality",
            value={
                "latency_ms": latency,
                "packet_loss": loss,
            },
        )


    return None



def generate_prediction(
    *,
    device: dict[str, Any],
    traffic: dict[str, Any],
    lte: dict[str, Any],
    ping: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate AI prediction from live network intelligence.

    H23.4.5.5.12.X.4.2
    Rule Based Prediction Core
    """


    events: list[dict[str, Any]] = []


    checks = [
        predict_cpu_risk(device),
        predict_traffic_risk(traffic),
        predict_lte_risk(lte),
        predict_link_risk(ping),
    ]


    for event in checks:

        if event:
            events.append(event)



    if events:

        max_confidence = max(
            event["confidence_percent"]
            for event in events
        )

        highest_severity = max(
            events,
            key=lambda x: (
                x["confidence_percent"]
            ),
        )


    else:

        max_confidence = 95

        highest_severity = None



    risk_score = (
        max_confidence
        if events
        else 5
    )


    return {

        "engine": {
            "name": ENGINE_NAME,
            "version": ENGINE_VERSION,
        },

        "generated_at": _utc_now(),

        "prediction_status": (
            "risk_detected"
            if events
            else "healthy"
        ),

        "risk_level": (
            _risk_level(
                risk_score
            )
            if events
            else "low"
        ),

        "confidence_percent": round(
            max_confidence,
            2,
        ),

        "event_count": len(events),

        "events": events,

        "recommended_action": (
            highest_severity[
                "recommendation"
            ]
            if highest_severity
            else
            "Continue monitoring."
        ),
    }
