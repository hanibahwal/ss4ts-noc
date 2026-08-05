"""
Trend Analyzer Engine

H23.4.5.5.12.X.4.2.2

Analyzes historical network behavior
and detects growth patterns.
"""

from __future__ import annotations

from typing import Dict, Any

from app.services.network_history_store import get_history


def calculate_growth(values):

    if len(values) < 2:
        return 0

    oldest = values[-1]
    newest = values[0]

    if oldest == 0:
        return 0

    return round(
        ((newest - oldest) / oldest) * 100,
        2
    )


def analyze_device(device_ip: str) -> Dict[str, Any]:

    history = get_history(
        device_ip,
        limit=100
    )

    if not history:
        return {
            "device_ip": device_ip,
            "status": "no_data"
        }

    traffic_values = [
        item["traffic_rx"] + item["traffic_tx"]
        for item in history
    ]

    cpu_values = [
        item["cpu"]
        for item in history
    ]

    traffic_growth = calculate_growth(
        traffic_values
    )

    cpu_growth = calculate_growth(
        cpu_values
    )

    risk = "LOW"

    if traffic_growth > 30:
        risk = "MEDIUM"

    if traffic_growth > 60:
        risk = "HIGH"

    return {
        "device_ip": device_ip,
        "samples": len(history),
        "traffic_growth_percent": traffic_growth,
        "cpu_growth_percent": cpu_growth,
        "risk": risk,
        "prediction":
            "Traffic increasing trend detected"
            if traffic_growth > 0
            else
            "Stable network behavior"
    }
