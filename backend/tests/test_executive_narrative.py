from __future__ import annotations

from app.services.executive_narrative import (
    build_executive_narrative,
)


def _intelligence(
    *,
    status: str = "healthy",
    score: int = 95,
    findings: list[dict] | None = None,
) -> dict:
    return {
        "router_ip": "192.168.45.99",
        "generated_at": (
            "2026-08-04T14:45:00+00:00"
        ),
        "status": status,
        "health_score": score,
        "confidence_percent": 100,
        "collector": {
            "device": {
                "reachable": True,
                "identity": "HANI-HOME-OFFICE",
                "cpu_usage_percent": 27,
                "memory_usage_percent": 72,
            },
            "traffic": {
                "selected_interface": (
                    "ether1-internet"
                ),
            },
            "ping": {
                "available": True,
                "reachable": True,
                "latency_ms": 1.3,
                "packet_loss_percent": 0,
            },
            "lte": {
                "available": True,
                "operator": "mobily",
                "data_class": "LTE",
                "rsrp_dbm": -71,
                "rsrq_db": -13,
                "sinr_db": 19,
            },
            "summary": {
                "available_sources": 5,
                "total_sources": 5,
                "selected_interface": (
                    "ether1-internet"
                ),
            },
        },
        "analysis": {
            "findings": findings or [],
        },
    }


def test_healthy_narrative() -> None:
    result = build_executive_narrative(
        _intelligence()
    )

    assert result["status"] == "healthy"
    assert result["health_score"] == 95
    assert result["priority"] == "low"

    assert (
        result["requires_immediate_action"]
        is False
    )

    assert (
        "درجة صحة 95 من 100"
        in result["executive_summary"]
    )

    assert (
        result["metrics"]["available_sources"]
        == 5
    )


def test_high_cpu_requires_action() -> None:
    result = build_executive_narrative(
        _intelligence(
            status="degraded",
            score=88,
            findings=[
                {
                    "code": "DEVICE_HIGH_CPU",
                    "severity": "high",
                    "value": 94,
                    "metric": (
                        "device.cpu_usage_percent"
                    ),
                },
            ],
        )
    )

    assert result["priority"] == "high"

    assert (
        result["requires_immediate_action"]
        is True
    )

    assert (
        result["key_observations"][0][
            "title"
        ]
        == "ارتفاع استخدام المعالج"
    )

    assert (
        "قواعد الجدار الناري"
        in result["recommended_actions"][0]
    )


def test_warning_does_not_require_immediate_action() -> None:
    result = build_executive_narrative(
        _intelligence(
            findings=[
                {
                    "code": "LTE_RSRQ_LOW",
                    "severity": "warning",
                    "value": -13,
                    "metric": "lte.rsrq_db",
                },
            ],
        )
    )

    assert result["priority"] == "medium"

    assert (
        result["requires_immediate_action"]
        is False
    )

    assert (
        "تحذير يحتاج إلى متابعة"
        in result["business_impact"]
    )


def test_critical_finding_has_priority() -> None:
    result = build_executive_narrative(
        _intelligence(
            status="critical",
            score=40,
            findings=[
                {
                    "code": "DEVICE_UNREACHABLE",
                    "severity": "critical",
                    "value": False,
                },
            ],
        )
    )

    assert result["priority"] == "critical"

    assert (
        result["requires_immediate_action"]
        is True
    )

    assert (
        "مؤشر حرج"
        in result["business_impact"]
    )


def test_unknown_finding_is_preserved() -> None:
    result = build_executive_narrative(
        _intelligence(
            findings=[
                {
                    "code": "CUSTOM_TEST",
                    "title": "Custom finding",
                    "severity": "info",
                    "recommendation": (
                        "Continue monitoring."
                    ),
                },
            ],
        )
    )

    observation = result[
        "key_observations"
    ][0]

    assert observation["code"] == "CUSTOM_TEST"
    assert observation["title"] == "Custom finding"
