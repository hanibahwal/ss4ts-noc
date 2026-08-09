from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from statistics import mean
from typing import Any


ENGINE_NAME = "SS4TS Decision Intelligence Engine"
ENGINE_VERSION = "1.6.1"


RISK_PRIORITY = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "healthy": 1,
    "unknown": 0,
}


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(numeric_value):
        return default

    return numeric_value


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(value, maximum),
    )


def _safe_round(
    value: Any,
    digits: int = 2,
) -> float:
    return round(
        _number(value),
        digits,
    )


def _parse_time(
    value: Any,
) -> datetime | None:
    if isinstance(value, datetime):
        return value

    if not value:
        return None

    text = str(value).strip()

    if text.endswith("Z"):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            text
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


def _risk_from_score(
    score: float,
) -> str:
    score = _clamp(score)

    if score >= 85:
        return "critical"

    if score >= 65:
        return "high"

    if score >= 40:
        return "medium"

    if score > 0:
        return "low"

    return "healthy"


def _create_signal(
    *,
    signal_id: str,
    category: str,
    title: str,
    description: str,
    risk: str,
    confidence: float,
    score: float,
    recommendation: str = "",
    interface_name: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": signal_id,
        "category": category,
        "title": title,
        "description": description,
        "risk": risk,
        "confidence": round(
            _clamp(confidence),
            2,
        ),
        "score": round(
            _clamp(score),
            2,
        ),
        "recommendation":
            recommendation,
        "interface_name":
            interface_name,
        "evidence":
            evidence or {},
    }


def _create_decision(
    *,
    decision_id: str,
    priority: str,
    title: str,
    action: str,
    reason: str,
    confidence: float,
    interface_name: str | None = None,
    expected_impact: str = "",
) -> dict[str, Any]:
    return {
        "id": decision_id,
        "priority": priority,
        "title": title,
        "action": action,
        "reason": reason,
        "confidence": round(
            _clamp(confidence),
            2,
        ),
        "interface_name":
            interface_name,
        "expected_impact":
            expected_impact,
    }


def _normalize_interface(
    item: dict[str, Any],
) -> dict[str, Any]:
    rx_bps = _number(
        item.get("rx_bps")
    )

    tx_bps = _number(
        item.get("tx_bps")
    )

    total_bps = _number(
        item.get(
            "total_bps",
            rx_bps + tx_bps,
        )
    )

    speed_bps = _number(
        item.get("speed_bps")
    )

    utilization = item.get(
        "utilization_percent"
    )

    utilization_percent = (
        None
        if utilization is None
        else _clamp(
            _number(utilization)
        )
    )

    rx_errors = _integer(
        item.get("rx_errors")
    )

    tx_errors = _integer(
        item.get("tx_errors")
    )

    total_errors = _integer(
        item.get(
            "total_errors",
            rx_errors + tx_errors,
        )
    )

    return {
        **item,
        "if_descr": str(
            item.get("if_descr")
            or item.get("name")
            or "unknown"
        ),
        "rx_bps": rx_bps,
        "tx_bps": tx_bps,
        "total_bps": total_bps,
        "speed_bps": speed_bps,
        "utilization_percent":
            utilization_percent,
        "rx_errors": rx_errors,
        "tx_errors": tx_errors,
        "total_errors": total_errors,
        "is_admin_up": bool(
            item.get(
                "is_admin_up",
                str(
                    item.get(
                        "admin_status",
                        "",
                    )
                ).lower() == "up",
            )
        ),
        "is_oper_up": bool(
            item.get(
                "is_oper_up",
                str(
                    item.get(
                        "oper_status",
                        "",
                    )
                ).lower() == "up",
            )
        ),
    }


def _normalize_history_points(
    points: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    normalized: list[
        dict[str, Any]
    ] = []

    for item in points or []:
        if not isinstance(item, dict):
            continue

        point_time = _parse_time(
            item.get("time")
            or item.get("_time")
            or item.get("timestamp")
        )

        rx_bps = _number(
            item.get("rx_bps")
        )

        tx_bps = _number(
            item.get("tx_bps")
        )

        total_bps = _number(
            item.get(
                "total_bps",
                rx_bps + tx_bps,
            )
        )

        normalized.append(
            {
                "time": point_time,
                "rx_bps": rx_bps,
                "tx_bps": tx_bps,
                "total_bps": total_bps,
            }
        )

    normalized.sort(
        key=lambda item: (
            item["time"]
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        )
    )

    return normalized


def _linear_trend(
    values: list[float],
) -> dict[str, Any]:
    clean_values = [
        _number(value)
        for value in values
        if isfinite(
            _number(value)
        )
    ]

    if len(clean_values) < 3:
        return {
            "available": False,
            "slope": 0.0,
            "direction": "unknown",
            "change_percent": 0.0,
            "confidence": 0.0,
        }

    count = len(clean_values)

    x_values = list(
        range(count)
    )

    x_mean = mean(x_values)
    y_mean = mean(clean_values)

    numerator = sum(
        (
            x_value - x_mean
        )
        * (
            y_value - y_mean
        )
        for x_value, y_value
        in zip(
            x_values,
            clean_values,
            strict=False,
        )
    )

    denominator = sum(
        (
            x_value - x_mean
        ) ** 2
        for x_value
        in x_values
    )

    slope = (
        numerator / denominator
        if denominator
        else 0.0
    )

    first_value = clean_values[0]
    last_value = clean_values[-1]

    change_percent = (
        (
            last_value - first_value
        )
        / abs(first_value)
        * 100.0
        if abs(first_value) > 0
        else 0.0
    )

    average_value = max(
        abs(y_mean),
        1.0,
    )

    normalized_slope = (
        slope / average_value
    )

    if normalized_slope > 0.03:
        direction = "rising"
    elif normalized_slope < -0.03:
        direction = "falling"
    else:
        direction = "stable"

    confidence = _clamp(
        min(
            95.0,
            45.0
            + count * 2.0
            + abs(
                normalized_slope
            )
            * 250.0,
        )
    )

    return {
        "available": True,
        "slope": round(
            slope,
            4,
        ),
        "direction": direction,
        "change_percent": round(
            change_percent,
            2,
        ),
        "confidence": round(
            confidence,
            2,
        ),
        "first_value":
            round(first_value, 2),
        "last_value":
            round(last_value, 2),
        "average_value":
            round(y_mean, 2),
    }


def _forecast_capacity(
    *,
    current_bps: float,
    slope_per_sample: float,
    capacity_bps: float,
    sample_seconds: int,
) -> dict[str, Any]:
    if capacity_bps <= 0:
        return {
            "available": False,
            "reason":
                "Interface capacity unavailable",
        }

    current_percent = (
        current_bps
        / capacity_bps
        * 100.0
    )

    target_bps = (
        capacity_bps * 0.9
    )

    if current_bps >= target_bps:
        return {
            "available": True,
            "already_above_threshold":
                True,
            "current_percent":
                round(
                    current_percent,
                    2,
                ),
            "threshold_percent": 90.0,
            "minutes_to_threshold": 0,
        }

    if slope_per_sample <= 0:
        return {
            "available": True,
            "already_above_threshold":
                False,
            "current_percent":
                round(
                    current_percent,
                    2,
                ),
            "threshold_percent": 90.0,
            "minutes_to_threshold":
                None,
            "direction": "not_rising",
        }

    samples_needed = (
        target_bps - current_bps
    ) / slope_per_sample

    seconds_needed = (
        samples_needed
        * max(
            sample_seconds,
            1,
        )
    )

    minutes_needed = (
        seconds_needed / 60.0
    )

    return {
        "available": True,
        "already_above_threshold":
            False,
        "current_percent":
            round(
                current_percent,
                2,
            ),
        "threshold_percent": 90.0,
        "minutes_to_threshold":
            round(
                max(
                    0.0,
                    minutes_needed,
                ),
                2,
            ),
        "direction": "rising",
    }


def _detect_traffic_signals(
    *,
    traffic_history:
        list[dict[str, Any]],
    interface_name: str | None,
    interface_speed_bps: float,
    sample_seconds: int,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    signals: list[
        dict[str, Any]
    ] = []

    total_values = [
        point["total_bps"]
        for point
        in traffic_history
    ]

    trend = _linear_trend(
        total_values
    )

    if not trend["available"]:
        return signals, {
            "trend": trend,
            "forecast": {
                "available": False,
                "reason":
                    "Insufficient history points",
            },
        }

    current_bps = (
        total_values[-1]
        if total_values
        else 0.0
    )

    forecast = _forecast_capacity(
        current_bps=current_bps,
        slope_per_sample=
            trend["slope"],
        capacity_bps=
            interface_speed_bps,
        sample_seconds=
            sample_seconds,
    )

    if (
        trend["direction"]
        == "rising"
        and trend[
            "change_percent"
        ] >= 25
    ):
        score = _clamp(
            35
            + abs(
                trend[
                    "change_percent"
                ]
            )
            * 0.45
        )

        signals.append(
            _create_signal(
                signal_id=(
                    "rapid-traffic-growth"
                ),
                category="traffic",
                title=(
                    "ارتفاع سريع في حركة الشبكة"
                ),
                description=(
                    "ارتفعت حركة الشبكة بنسبة "
                    f"{trend['change_percent']:.2f}% "
                    "خلال الفترة المحددة."
                ),
                risk=_risk_from_score(
                    score
                ),
                confidence=
                    trend["confidence"],
                score=score,
                recommendation=(
                    "افحص Top Talkers وQueues "
                    "والاتصالات الجديدة على الرابط."
                ),
                interface_name=
                    interface_name,
                evidence={
                    "trend": trend,
                    "current_bps":
                        current_bps,
                },
            )
        )

    minutes_to_threshold = (
        forecast.get(
            "minutes_to_threshold"
        )
        if forecast.get(
            "available"
        )
        else None
    )

    if (
        minutes_to_threshold
        is not None
        and minutes_to_threshold
        <= 60
    ):
        score = (
            90
            if minutes_to_threshold
            <= 10
            else 75
            if minutes_to_threshold
            <= 30
            else 60
        )

        signals.append(
            _create_signal(
                signal_id=(
                    "capacity-threshold-forecast"
                ),
                category="capacity",
                title=(
                    "توقع اقتراب الرابط من التشبع"
                ),
                description=(
                    "وفق الاتجاه الحالي، قد تصل "
                    "الواجهة إلى 90% من سعتها خلال "
                    f"{minutes_to_threshold:.1f} دقيقة."
                ),
                risk=_risk_from_score(
                    score
                ),
                confidence=min(
                    95,
                    trend["confidence"],
                ),
                score=score,
                recommendation=(
                    "راقب الرابط فورًا، وافحص "
                    "توزيع الحمل أو ارفع السعة."
                ),
                interface_name=
                    interface_name,
                evidence={
                    "forecast":
                        forecast,
                    "trend": trend,
                },
            )
        )

    return signals, {
        "trend": trend,
        "forecast": forecast,
    }


def _detect_interface_signals(
    interfaces: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    signals: list[
        dict[str, Any]
    ] = []

    for interface in interfaces:
        interface_name = (
            interface["if_descr"]
        )

        utilization = interface[
            "utilization_percent"
        ]

        total_errors = interface[
            "total_errors"
        ]

        if (
            utilization is not None
            and utilization >= 90
        ):
            signals.append(
                _create_signal(
                    signal_id=(
                        "interface-saturation-"
                        f"{interface_name}"
                    ),
                    category="capacity",
                    title=(
                        "تشبع حرج في الواجهة"
                    ),
                    description=(
                        f"استخدام {interface_name} "
                        f"بلغ {utilization:.2f}%."
                    ),
                    risk="critical",
                    confidence=99,
                    score=95,
                    recommendation=(
                        "افحص Top Talkers وارفع "
                        "السعة أو وزع الحركة فورًا."
                    ),
                    interface_name=
                        interface_name,
                    evidence={
                        "utilization_percent":
                            utilization,
                        "speed_bps":
                            interface[
                                "speed_bps"
                            ],
                    },
                )
            )

        elif (
            utilization is not None
            and utilization >= 75
        ):
            signals.append(
                _create_signal(
                    signal_id=(
                        "interface-high-load-"
                        f"{interface_name}"
                    ),
                    category="capacity",
                    title=(
                        "استخدام مرتفع في الواجهة"
                    ),
                    description=(
                        f"استخدام {interface_name} "
                        f"بلغ {utilization:.2f}%."
                    ),
                    risk="high",
                    confidence=97,
                    score=72,
                    recommendation=(
                        "راقب ساعات الذروة وافحص "
                        "إمكانية توزيع الحركة."
                    ),
                    interface_name=
                        interface_name,
                    evidence={
                        "utilization_percent":
                            utilization,
                    },
                )
            )

        if total_errors >= 100:
            signals.append(
                _create_signal(
                    signal_id=(
                        "interface-failure-risk-"
                        f"{interface_name}"
                    ),
                    category="failure",
                    title=(
                        "احتمال فشل مرتفع للواجهة"
                    ),
                    description=(
                        f"تم اكتشاف {total_errors} "
                        f"خطأ على {interface_name}."
                    ),
                    risk="critical",
                    confidence=96,
                    score=92,
                    recommendation=(
                        "افحص الكابل وDuplex وSFP "
                        "والطرف المقابل فورًا."
                    ),
                    interface_name=
                        interface_name,
                    evidence={
                        "total_errors":
                            total_errors,
                        "rx_errors":
                            interface[
                                "rx_errors"
                            ],
                        "tx_errors":
                            interface[
                                "tx_errors"
                            ],
                    },
                )
            )

        elif total_errors >= 20:
            signals.append(
                _create_signal(
                    signal_id=(
                        "interface-errors-high-"
                        f"{interface_name}"
                    ),
                    category="failure",
                    title=(
                        "ارتفاع أخطاء الواجهة"
                    ),
                    description=(
                        f"يوجد {total_errors} خطأ "
                        f"على {interface_name}."
                    ),
                    risk="high",
                    confidence=94,
                    score=70,
                    recommendation=(
                        "افحص جودة الرابط والكابل "
                        "وMTU وDuplex."
                    ),
                    interface_name=
                        interface_name,
                    evidence={
                        "total_errors":
                            total_errors,
                    },
                )
            )

        elif total_errors > 0:
            signals.append(
                _create_signal(
                    signal_id=(
                        "interface-errors-notice-"
                        f"{interface_name}"
                    ),
                    category="failure",
                    title=(
                        "أخطاء محدودة في الواجهة"
                    ),
                    description=(
                        f"تم تسجيل {total_errors} "
                        f"أخطاء على {interface_name}."
                    ),
                    risk="low",
                    confidence=90,
                    score=28,
                    recommendation=(
                        "استمر في المراقبة، وافحص "
                        "الرابط إذا استمرت الزيادة."
                    ),
                    interface_name=
                        interface_name,
                    evidence={
                        "total_errors":
                            total_errors,
                    },
                )
            )

        if (
            interface["is_admin_up"]
            and not interface[
                "is_oper_up"
            ]
        ):
            normalized_name = (
                interface_name or ""
            ).lower()

            total_bps = float(
                interface.get(
                    "total_bps",
                    0,
                )
                or 0
            )

            speed_bps = float(
                interface.get(
                    "speed_bps",
                    0,
                )
                or 0
            )

            looks_important = any(
                marker in normalized_name
                for marker in (
                    "wan",
                    "uplink",
                    "backhaul",
                    "internet",
                    "isp",
                    "trunk",
                )
            )

            should_alert = (
                total_bps > 0
                or speed_bps > 0
                or looks_important
            )

            if should_alert:
                signals.append(
                    _create_signal(
                        signal_id=(
                            "link-down-"
                            f"{interface_name}"
                        ),
                        category="availability",
                        title=(
                            "واجهة مفعلة لكنها متوقفة"
                        ),
                        description=(
                            f"{interface_name} في حالة "
                            "Admin Up / Oper Down."
                        ),
                        risk="medium",
                        confidence=92,
                        score=52,
                        recommendation=(
                            "تحقق من الكابل والطرف "
                            "المقابل وPoE وSFP."
                        ),
                        interface_name=
                            interface_name,
                        evidence={
                            "admin_up": True,
                            "oper_up": False,
                            "speed_bps": speed_bps,
                            "total_bps": total_bps,
                            "important_name":
                                looks_important,
                        },
                    )
                )

    return signals


def _detect_correlation_signals(
    *,
    cpu_usage: float | None,
    memory_usage: float | None,
    traffic_trend:
        dict[str, Any],
    interfaces: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    signals: list[
        dict[str, Any]
    ] = []

    cpu = (
        None
        if cpu_usage is None
        else _clamp(
            _number(cpu_usage)
        )
    )

    memory = (
        None
        if memory_usage is None
        else _clamp(
            _number(memory_usage)
        )
    )

    interfaces_with_errors = [
        item
        for item in interfaces
        if item["total_errors"] > 0
    ]

    high_utilization = [
        item
        for item in interfaces
        if (
            item[
                "utilization_percent"
            ]
            is not None
            and item[
                "utilization_percent"
            ] >= 75
        )
    ]

    traffic_rising = (
        traffic_trend.get(
            "direction"
        ) == "rising"
        and traffic_trend.get(
            "change_percent",
            0,
        ) >= 20
    )

    if (
        cpu is not None
        and cpu >= 80
        and traffic_rising
    ):
        confidence = _clamp(
            75
            + min(
                20,
                (
                    cpu - 80
                )
                * 1.2,
            )
        )

        signals.append(
            _create_signal(
                signal_id=(
                    "cpu-traffic-correlation"
                ),
                category="correlation",
                title=(
                    "ارتباط بين ارتفاع CPU والحركة"
                ),
                description=(
                    "ارتفع استخدام المعالج بالتزامن "
                    "مع زيادة حركة الشبكة."
                ),
                risk=(
                    "critical"
                    if cpu >= 95
                    else "high"
                ),
                confidence=confidence,
                score=(
                    90
                    if cpu >= 95
                    else 72
                ),
                recommendation=(
                    "افحص Connection Tracking "
                    "وQueues وFirewall وTop Talkers."
                ),
                evidence={
                    "cpu_usage": cpu,
                    "traffic_trend":
                        traffic_trend,
                },
            )
        )

    if (
        traffic_rising
        and interfaces_with_errors
    ):
        affected = [
            item["if_descr"]
            for item
            in interfaces_with_errors
        ]

        signals.append(
            _create_signal(
                signal_id=(
                    "traffic-errors-correlation"
                ),
                category="correlation",
                title=(
                    "ارتباط بين زيادة الحركة والأخطاء"
                ),
                description=(
                    "زادت حركة الشبكة بالتزامن "
                    "مع ظهور أخطاء في الواجهات."
                ),
                risk="high",
                confidence=88,
                score=76,
                recommendation=(
                    "افحص جودة الروابط وDuplex "
                    "وMTU قبل زيادة السعة."
                ),
                interface_name=(
                    affected[0]
                    if affected
                    else None
                ),
                evidence={
                    "interfaces":
                        affected,
                    "traffic_trend":
                        traffic_trend,
                },
            )
        )

    if (
        cpu is not None
        and cpu >= 85
        and memory is not None
        and memory < 75
        and traffic_rising
    ):
        signals.append(
            _create_signal(
                signal_id=(
                    "processing-bottleneck"
                ),
                category="root_cause",
                title=(
                    "اختناق معالجة محتمل"
                ),
                description=(
                    "المعالج مرتفع والذاكرة مستقرة "
                    "مع زيادة في حركة الشبكة، مما "
                    "يشير إلى حمل معالجة وليس نقص ذاكرة."
                ),
                risk="high",
                confidence=86,
                score=74,
                recommendation=(
                    "افحص Firewall وQueues "
                    "وConnection Tracking وFastTrack."
                ),
                evidence={
                    "cpu_usage": cpu,
                    "memory_usage":
                        memory,
                    "traffic_rising":
                        traffic_rising,
                },
            )
        )

    if (
        len(high_utilization) >= 2
        and cpu is not None
        and cpu >= 80
    ):
        signals.append(
            _create_signal(
                signal_id=(
                    "multi-interface-congestion"
                ),
                category="root_cause",
                title=(
                    "ازدحام متعدد الواجهات"
                ),
                description=(
                    "تم اكتشاف أكثر من واجهة "
                    "مرتفعة الاستخدام مع ارتفاع CPU."
                ),
                risk="critical",
                confidence=91,
                score=89,
                recommendation=(
                    "افحص Broadcast/Multicast، "
                    "Loops، Bridge وQueue Tree."
                ),
                evidence={
                    "interfaces": [
                        item["if_descr"]
                        for item
                        in high_utilization
                    ],
                    "cpu_usage": cpu,
                },
            )
        )

    return signals


def _build_decisions(
    signals: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    decisions: list[
        dict[str, Any]
    ] = []

    seen_actions: set[str] = set()

    sorted_signals = sorted(
        signals,
        key=lambda item: (
            RISK_PRIORITY.get(
                item["risk"],
                0,
            ),
            item["score"],
            item["confidence"],
        ),
        reverse=True,
    )

    for signal in sorted_signals:
        action = str(
            signal.get(
                "recommendation"
            )
            or ""
        ).strip()

        if not action:
            continue

        unique_key = action.lower()

        if unique_key in seen_actions:
            continue

        seen_actions.add(
            unique_key
        )

        priority = (
            "urgent"
            if signal["risk"]
            == "critical"
            else "high"
            if signal["risk"]
            == "high"
            else "medium"
            if signal["risk"]
            == "medium"
            else "low"
        )

        decisions.append(
            _create_decision(
                decision_id=(
                    "decision-"
                    f"{signal['id']}"
                ),
                priority=priority,
                title=signal["title"],
                action=action,
                reason=(
                    signal[
                        "description"
                    ]
                ),
                confidence=(
                    signal[
                        "confidence"
                    ]
                ),
                interface_name=(
                    signal[
                        "interface_name"
                    ]
                ),
                expected_impact=(
                    "تقليل الخطر وتحسين "
                    "استقرار الشبكة."
                ),
            )
        )

    if not decisions:
        decisions.append(
            _create_decision(
                decision_id=(
                    "decision-continue-monitoring"
                ),
                priority="low",
                title=(
                    "لا توجد إجراءات عاجلة"
                ),
                action=(
                    "استمر في المراقبة الدورية."
                ),
                reason=(
                    "لم يتم اكتشاف إشارات خطر "
                    "تتطلب تدخلًا حاليًا."
                ),
                confidence=95,
                expected_impact=(
                    "المحافظة على الاستقرار."
                ),
            )
        )

    return decisions[:10]


def _build_executive_summary(
    *,
    signals: list[
        dict[str, Any]
    ],
    decisions: list[
        dict[str, Any]
    ],
) -> str:
    if not signals:
        return (
            "لم يتم اكتشاف مخاطر تشغيلية مؤثرة. "
            "الشبكة مستقرة وفق البيانات الحالية."
        )

    sorted_signals = sorted(
        signals,
        key=lambda item: (
            RISK_PRIORITY.get(
                item["risk"],
                0,
            ),
            item["score"],
        ),
        reverse=True,
    )

    top_signal = sorted_signals[0]

    top_decision = (
        decisions[0]
        if decisions
        else None
    )

    summary = (
        f"أهم خطر حالي هو: "
        f"{top_signal['title']}. "
        f"مستوى الخطر "
        f"{top_signal['risk']} "
        f"وبنسبة ثقة "
        f"{top_signal['confidence']:.0f}%."
    )

    if top_decision:
        summary += (
            " الإجراء المقترح: "
            f"{top_decision['action']}"
        )

    return summary


def analyze_decision_intelligence(
    *,
    router_ip: str,
    device_name: str | None = None,
    cpu_usage: float | None = None,
    memory_usage: float | None = None,
    interfaces: list[
        dict[str, Any]
    ] | None = None,
    traffic_history: list[
        dict[str, Any]
    ] | None = None,
    selected_interface:
        str | None = None,
    sample_seconds: int = 10,
) -> dict[str, Any]:
    normalized_interfaces = [
        _normalize_interface(
            item
        )
        for item
        in (
            interfaces or []
        )
        if isinstance(
            item,
            dict,
        )
    ]

    normalized_history = (
        _normalize_history_points(
            traffic_history
        )
    )

    selected = None

    if selected_interface:
        selected = next(
            (
                item
                for item
                in normalized_interfaces
                if item["if_descr"]
                == selected_interface
            ),
            None,
        )

    if selected is None:
        selected = max(
            normalized_interfaces,
            key=lambda item: (
                item["total_bps"]
            ),
            default=None,
        )

    selected_name = (
        selected["if_descr"]
        if selected
        else selected_interface
    )

    selected_speed = (
        selected["speed_bps"]
        if selected
        else 0.0
    )

    signals: list[
        dict[str, Any]
    ] = []

    traffic_signals, traffic_analysis = (
        _detect_traffic_signals(
            traffic_history=
                normalized_history,
            interface_name=
                selected_name,
            interface_speed_bps=
                selected_speed,
            sample_seconds=
                sample_seconds,
        )
    )

    signals.extend(
        traffic_signals
    )

    signals.extend(
        _detect_interface_signals(
            normalized_interfaces
        )
    )

    signals.extend(
        _detect_correlation_signals(
            cpu_usage=cpu_usage,
            memory_usage=
                memory_usage,
            traffic_trend=
                traffic_analysis[
                    "trend"
                ],
            interfaces=
                normalized_interfaces,
        )
    )

    signals.sort(
        key=lambda item: (
            RISK_PRIORITY.get(
                item["risk"],
                0,
            ),
            item["score"],
            item["confidence"],
        ),
        reverse=True,
    )

    decisions = _build_decisions(
        signals
    )

    top_signal = (
        signals[0]
        if signals
        else None
    )

    overall_risk = (
        top_signal["risk"]
        if top_signal
        else "healthy"
    )

    overall_score = (
        top_signal["score"]
        if top_signal
        else 0.0
    )

    return {
        "router_ip": router_ip,
        "device_name": (
            device_name
            or router_ip
        ),
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "engine": {
            "name": ENGINE_NAME,
            "version":
                ENGINE_VERSION,
            "mode": (
                "explainable-decision-intelligence"
            ),
        },

        "risk": {
            "level":
                overall_risk,
            "score":
                overall_score,
            "label": {
                "critical": "حرج",
                "high": "مرتفع",
                "medium": "متوسط",
                "low": "منخفض",
                "healthy": "مستقر",
            }.get(
                overall_risk,
                "غير معروف",
            ),
        },

        "executive_summary":
            _build_executive_summary(
                signals=signals,
                decisions=decisions,
            ),

        "top_signal":
            top_signal,

        "signals":
            signals,

        "decisions":
            decisions,

        "traffic_analysis":
            traffic_analysis,

        "statistics": {
            "signal_count":
                len(signals),
            "decision_count":
                len(decisions),
            "critical_signals":
                sum(
                    1
                    for signal
                    in signals
                    if signal["risk"]
                    == "critical"
                ),
            "high_signals":
                sum(
                    1
                    for signal
                    in signals
                    if signal["risk"]
                    == "high"
                ),
            "medium_signals":
                sum(
                    1
                    for signal
                    in signals
                    if signal["risk"]
                    == "medium"
                ),
            "interfaces_analyzed":
                len(
                    normalized_interfaces
                ),
            "history_points":
                len(
                    normalized_history
                ),
        },

        "analysis_context": {
            "selected_interface":
                selected_name,
            "sample_seconds":
                sample_seconds,
            "cpu_usage":
                cpu_usage,
            "memory_usage":
                memory_usage,
            "interface_speed_bps":
                selected_speed,
        },
    }

# Integration flag: ready for Executive Notification bridge
EXECUTIVE_NOTIFICATION_READY = True
