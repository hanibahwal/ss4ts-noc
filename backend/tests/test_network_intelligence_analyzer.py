from __future__ import annotations

from copy import deepcopy

from app.services.network_intelligence_analyzer import (
    analyze_network_intelligence,
)


def _collector_sample() -> dict:
    return {
        "device": {
            "reachable": True,
            "cpu_usage_percent": 20.0,
            "memory_usage_percent": 40.0,
            "temperature_celsius": 45.0,
        },
        "traffic": {
            "selected_interface": "ether1-internet",
            "total_bps": 2_000_000.0,
            "history": {
                "points": [
                    {"total_bps": 1_900_000.0},
                    {"total_bps": 2_000_000.0},
                    {"total_bps": 2_100_000.0},
                    {"total_bps": 2_000_000.0},
                    {"total_bps": 1_950_000.0},
                    {"total_bps": 2_050_000.0},
                ],
            },
        },
        "ping": {
            "available": True,
            "reachable": True,
            "latency_ms": 2.0,
            "packet_loss_percent": 0.0,
        },
        "lte": {
            "available": True,
            "running": True,
            "operator": "mobily",
            "data_class": "LTE",
            "primary_band": "B41@20Mhz",
            "cell_id": "111454211",
            "rsrp_dbm": -71,
            "rsrq_db": -10,
            "sinr_db": 20,
            "rssi_dbm": -40,
        },
    }


def _finding_codes(result: dict) -> set[str]:
    return {
        finding["code"]
        for finding in result["findings"]
    }


def test_healthy_network_scores_excellent() -> None:
    result = analyze_network_intelligence(
        _collector_sample()
    )

    assert result["overall_health_score"] == 100
    assert result["overall_health"] == "excellent"
    assert result["confidence_percent"] == 100
    assert result["findings"] == []
    assert result["recommendations"] == []


def test_critical_cpu_creates_finding() -> None:
    collector = _collector_sample()
    collector["device"]["cpu_usage_percent"] = 100.0

    result = analyze_network_intelligence(collector)

    assert (
        result["components"]["device"]["score"]
        == 55
    )
    assert (
        result["components"]["device"]["health"]
        == "degraded"
    )
    assert "DEVICE_HIGH_CPU" in _finding_codes(result)

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "DEVICE_HIGH_CPU"
    )

    assert finding["severity"] == "critical"
    assert finding["value"] == 100.0
    assert finding["threshold"] == 70


def test_degraded_lte_rsrq_creates_warning() -> None:
    collector = _collector_sample()
    collector["lte"]["rsrq_db"] = -14

    result = analyze_network_intelligence(collector)

    assert result["components"]["lte"]["score"] == 85
    assert result["components"]["lte"]["health"] == "healthy"
    assert "LTE_RSRQ_LOW" in _finding_codes(result)

    finding = next(
        item
        for item in result["findings"]
        if item["code"] == "LTE_RSRQ_LOW"
    )

    assert finding["severity"] == "warning"
    assert finding["value"] == -14.0
    assert finding["threshold"] == -12


def test_unreachable_ping_is_critical() -> None:
    collector = _collector_sample()
    collector["ping"]["reachable"] = False

    result = analyze_network_intelligence(collector)

    assert result["components"]["ping"]["score"] == 0
    assert (
        result["components"]["ping"]["health"]
        == "critical"
    )
    assert "PING_UNREACHABLE" in _finding_codes(result)


def test_missing_lte_reduces_confidence() -> None:
    collector = _collector_sample()
    collector["lte"] = {
        "available": False,
    }

    result = analyze_network_intelligence(collector)

    assert result["confidence_percent"] == 65
    assert (
        result["components"]["lte"]["available"]
        is False
    )
    assert "LTE_UNAVAILABLE" in _finding_codes(result)


def test_input_is_not_modified() -> None:
    collector = _collector_sample()
    original = deepcopy(collector)

    analyze_network_intelligence(collector)

    assert collector == original


def test_invalid_input_is_rejected() -> None:
    try:
        analyze_network_intelligence([])
    except TypeError as exc:
        assert "dictionary" in str(exc)
    else:
        raise AssertionError(
            "TypeError was not raised"
        )


def test_critical_finding_caps_overall_health() -> None:
    collector = _collector_sample()
    collector["device"]["cpu_usage_percent"] = 100.0

    result = analyze_network_intelligence(
        collector
    )

    assert result["overall_health"] == "critical"
    assert result["overall_health_score"] > 0
    assert "DEVICE_HIGH_CPU" in _finding_codes(
        result
    )


def test_warning_finding_caps_health_at_healthy() -> None:
    collector = _collector_sample()
    collector["lte"]["rsrq_db"] = -14

    result = analyze_network_intelligence(
        collector
    )

    assert result["overall_health"] == "healthy"
    assert "LTE_RSRQ_LOW" in _finding_codes(
        result
    )


def test_low_confidence_blocks_healthy_status() -> None:
    collector = _collector_sample()

    collector["device"] = {
        "reachable": False,
    }
    collector["lte"] = {
        "available": False,
    }

    result = analyze_network_intelligence(
        collector
    )

    assert result["confidence_percent"] == 45
    assert result["overall_health"] == "unavailable"
