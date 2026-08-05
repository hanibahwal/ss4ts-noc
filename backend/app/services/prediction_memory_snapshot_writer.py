from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.prediction_store import save_prediction


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_prediction_snapshot(
    *,
    device_ip: str,
    device_name: str,
    health_score: float,
    confidence_percent: float,
    status: str,
    cpu: float = 0,
    memory: float = 0,
    traffic_rx: float = 0,
    traffic_tx: float = 0,
    latency: float = 0,
    packet_loss: float = 0,
    signal: float = 0,
) -> None:
    """
    Save AI prediction memory snapshot.

    This creates historical memory for future
    predictive intelligence.
    """

    payload: dict[str, Any] = {
        "device_ip": device_ip,
        "device_name": device_name,
        "health_score": health_score,
        "confidence_percent": confidence_percent,
        "status": status,
        "cpu": cpu,
        "memory": memory,
        "traffic_rx": traffic_rx,
        "traffic_tx": traffic_tx,
        "latency": latency,
        "packet_loss": packet_loss,
        "signal": signal,
        "created_at": _utc_now(),
    }

    try:
        save_prediction(payload)

    except Exception:
        # Memory writer must never stop collector
        pass
