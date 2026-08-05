from __future__ import annotations

from statistics import mean
from typing import Any

from app.models.network_intelligence_analysis import (
    ComponentAnalysis,
    FindingSeverity,
    HealthState,
    IntelligenceFinding,
    NetworkIntelligenceAnalysis,
    TrendState,
)


ANALYZER_NAME = (
    "SS4TS Network Intelligence Analysis Engine"
)
ANALYZER_VERSION = "1.0.0"


WEIGHTS = {
    "device": 0.20,
    "traffic": 0.20,
    "ping": 0.25,
    "lte": 0.35,
}


def _number(
    value: Any,
    default: float | None = None,
) -> float | None:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _health_from_score(score: float) -> HealthState:
    if score >= 90:
        return HealthState.EXCELLENT

    if score >= 75:
        return HealthState.HEALTHY

    if score >= 50:
        return HealthState.DEGRADED

    return HealthState.CRITICAL


def _analyze_device(
    collector: dict[str, Any],
) -> tuple[
    ComponentAnalysis,
    list[IntelligenceFinding],
]:
    device = collector.get("device") or {}
    findings: list[IntelligenceFinding] = []

    if not device.get("reachable"):
        findings.append(
            IntelligenceFinding(
                code="DEVICE_UNREACHABLE",
                title="Router unreachable",
                severity=FindingSeverity.CRITICAL,
                message=(
                    "The primary router could not be reached."
                ),
                metric="device.reachable",
                value=False,
                threshold=True,
                recommendation=(
                    "Check power, routing, VPN connectivity "
                    "and RouterOS API access."
                ),
            )
        )

        return (
            ComponentAnalysis(
                name="device",
                available=False,
                score=0,
                health=HealthState.CRITICAL,
                details={
                    "reachable": False,
                },
            ),
            findings,
        )

    score = 100

    cpu = _number(
        device.get("cpu_usage_percent")
    )
    memory = _number(
        device.get("memory_usage_percent")
    )
    temperature = _number(
        device.get("temperature_celsius")
    )

    if cpu is not None:
        if cpu >= 95:
            score -= 45
            severity = FindingSeverity.CRITICAL
        elif cpu >= 85:
            score -= 30
            severity = FindingSeverity.HIGH
        elif cpu >= 70:
            score -= 15
            severity = FindingSeverity.WARNING
        else:
            severity = None

        if severity is not None:
            findings.append(
                IntelligenceFinding(
                    code="DEVICE_HIGH_CPU",
                    title="High router CPU usage",
                    severity=severity,
                    message=(
                        f"Router CPU usage is {cpu:.1f}%."
                    ),
                    metric="device.cpu_usage_percent",
                    value=cpu,
                    threshold=70,
                    recommendation=(
                        "Review firewall rules, queues, "
                        "connection tracking and traffic load."
                    ),
                )
            )

    if memory is not None:
        if memory >= 95:
            score -= 35
            severity = FindingSeverity.CRITICAL
        elif memory >= 85:
            score -= 20
            severity = FindingSeverity.HIGH
        elif memory >= 75:
            score -= 10
            severity = FindingSeverity.WARNING
        else:
            severity = None

        if severity is not None:
            findings.append(
                IntelligenceFinding(
                    code="DEVICE_HIGH_MEMORY",
                    title="High memory usage",
                    severity=severity,
                    message=(
                        f"Router memory usage is "
                        f"{memory:.1f}%."
                    ),
                    metric="device.memory_usage_percent",
                    value=memory,
                    threshold=75,
                    recommendation=(
                        "Review active services, sessions "
                        "and RouterOS resource consumption."
                    ),
                )
            )

    if temperature is not None:
        if temperature >= 85:
            score -= 35
            severity = FindingSeverity.CRITICAL
        elif temperature >= 75:
            score -= 20
            severity = FindingSeverity.HIGH
        elif temperature >= 65:
            score -= 10
            severity = FindingSeverity.WARNING
        else:
            severity = None

        if severity is not None:
            findings.append(
                IntelligenceFinding(
                    code="DEVICE_HIGH_TEMPERATURE",
                    title="High device temperature",
                    severity=severity,
                    message=(
                        f"Router temperature is "
                        f"{temperature:.1f}°C."
                    ),
                    metric="device.temperature_celsius",
                    value=temperature,
                    threshold=65,
                    recommendation=(
                        "Check ventilation, cooling and "
                        "equipment-room temperature."
                    ),
                )
            )

    return (
        ComponentAnalysis(
            name="device",
            available=True,
            score=score,
            health=_health_from_score(score),
            details={
                "reachable": True,
                "cpu_usage_percent": cpu,
                "memory_usage_percent": memory,
                "temperature_celsius": temperature,
            },
        ),
        findings,
    )


def _traffic_points(
    traffic: dict[str, Any],
) -> list[float]:
    history = traffic.get("history") or {}
    points = history.get("points") or []

    values: list[float] = []

    for point in points:
        if not isinstance(point, dict):
            continue

        value = _number(
            point.get(
                "total_bps",
                point.get("value"),
            )
        )

        if value is not None:
            values.append(value)

    return values


def _traffic_trend(
    values: list[float],
) -> TrendState:
    if len(values) < 6:
        return TrendState.UNKNOWN

    segment_size = max(2, len(values) // 3)

    first = mean(values[:segment_size])
    last = mean(values[-segment_size:])

    baseline = max(first, 1.0)
    change_percent = (
        (last - first) / baseline
    ) * 100.0

    if change_percent >= 20:
        return TrendState.RISING

    if change_percent <= -20:
        return TrendState.FALLING

    return TrendState.STABLE


def _analyze_traffic(
    collector: dict[str, Any],
) -> tuple[
    ComponentAnalysis,
    list[IntelligenceFinding],
]:
    traffic = collector.get("traffic") or {}
    findings: list[IntelligenceFinding] = []

    interface = traffic.get("selected_interface")
    total_bps = _number(
        traffic.get("total_bps"),
        0.0,
    ) or 0.0

    points = _traffic_points(traffic)
    trend = _traffic_trend(points)

    available = bool(interface)

    if not available:
        findings.append(
            IntelligenceFinding(
                code="TRAFFIC_UNAVAILABLE",
                title="Traffic data unavailable",
                severity=FindingSeverity.WARNING,
                message=(
                    "No primary traffic interface was selected."
                ),
                metric="traffic.selected_interface",
                value=None,
                recommendation=(
                    "Check SNMP collection and interface "
                    "selection rules."
                ),
            )
        )

        return (
            ComponentAnalysis(
                name="traffic",
                available=False,
                score=40,
                health=HealthState.DEGRADED,
                details={
                    "selected_interface": None,
                    "trend": TrendState.UNKNOWN.value,
                },
            ),
            findings,
        )

    score = 100

    if not points:
        score -= 15
        findings.append(
            IntelligenceFinding(
                code="TRAFFIC_HISTORY_MISSING",
                title="Traffic history unavailable",
                severity=FindingSeverity.NOTICE,
                message=(
                    "Current traffic is available, but no "
                    "history points were available."
                ),
                metric="traffic.history.points",
                value=0,
                recommendation=(
                    "Verify InfluxDB traffic-history "
                    "retention and queries."
                ),
            )
        )

    if trend == TrendState.RISING:
        score -= 5
        findings.append(
            IntelligenceFinding(
                code="TRAFFIC_RISING",
                title="Traffic load is rising",
                severity=FindingSeverity.INFO,
                message=(
                    "Traffic has increased by at least 20% "
                    "across the analysis window."
                ),
                metric="traffic.trend",
                value=trend.value,
                recommendation=(
                    "Continue monitoring capacity and "
                    "interface utilization."
                ),
            )
        )

    return (
        ComponentAnalysis(
            name="traffic",
            available=True,
            score=score,
            health=_health_from_score(score),
            details={
                "selected_interface": interface,
                "current_total_bps": total_bps,
                "history_points": len(points),
                "trend": trend.value,
            },
        ),
        findings,
    )


def _analyze_ping(
    collector: dict[str, Any],
) -> tuple[
    ComponentAnalysis,
    list[IntelligenceFinding],
]:
    ping = collector.get("ping") or {}
    findings: list[IntelligenceFinding] = []

    available = ping.get("available") is True
    reachable = ping.get("reachable") is True

    if not available:
        findings.append(
            IntelligenceFinding(
                code="PING_UNAVAILABLE",
                title="Ping metrics unavailable",
                severity=FindingSeverity.WARNING,
                message=(
                    "Latency and packet-loss data are "
                    "not available."
                ),
                recommendation=(
                    "Check Telegraf Ping and InfluxDB."
                ),
            )
        )

        return (
            ComponentAnalysis(
                name="ping",
                available=False,
                score=30,
                health=HealthState.DEGRADED,
            ),
            findings,
        )

    latency = _number(ping.get("latency_ms"))
    packet_loss = _number(
        ping.get("packet_loss_percent"),
        100.0,
    ) or 0.0

    score = 100

    if not reachable:
        score = 0
        findings.append(
            IntelligenceFinding(
                code="PING_UNREACHABLE",
                title="Ping target unreachable",
                severity=FindingSeverity.CRITICAL,
                message=(
                    "The monitored router is not responding "
                    "to Ping."
                ),
                metric="ping.reachable",
                value=False,
                threshold=True,
                recommendation=(
                    "Check routing, firewall rules and "
                    "device availability immediately."
                ),
            )
        )
    else:
        if packet_loss >= 50:
            score -= 70
            severity = FindingSeverity.CRITICAL
        elif packet_loss >= 10:
            score -= 45
            severity = FindingSeverity.HIGH
        elif packet_loss >= 2:
            score -= 25
            severity = FindingSeverity.WARNING
        elif packet_loss > 0:
            score -= 10
            severity = FindingSeverity.NOTICE
        else:
            severity = None

        if severity is not None:
            findings.append(
                IntelligenceFinding(
                    code="PING_PACKET_LOSS",
                    title="Packet loss detected",
                    severity=severity,
                    message=(
                        f"Packet loss is "
                        f"{packet_loss:.2f}%."
                    ),
                    metric="ping.packet_loss_percent",
                    value=packet_loss,
                    threshold=2,
                    recommendation=(
                        "Check wireless quality, congestion, "
                        "routing and physical links."
                    ),
                )
            )

        if latency is not None:
            if latency >= 200:
                score -= 50
                severity = FindingSeverity.CRITICAL
            elif latency >= 100:
                score -= 30
                severity = FindingSeverity.HIGH
            elif latency >= 50:
                score -= 15
                severity = FindingSeverity.WARNING
            elif latency >= 20:
                score -= 5
                severity = FindingSeverity.NOTICE
            else:
                severity = None

            if severity is not None:
                findings.append(
                    IntelligenceFinding(
                        code="PING_HIGH_LATENCY",
                        title="Elevated latency",
                        severity=severity,
                        message=(
                            f"Average latency is "
                            f"{latency:.2f} ms."
                        ),
                        metric="ping.latency_ms",
                        value=latency,
                        threshold=20,
                        recommendation=(
                            "Review path quality, congestion "
                            "and uplink performance."
                        ),
                    )
                )

    return (
        ComponentAnalysis(
            name="ping",
            available=True,
            score=score,
            health=_health_from_score(score),
            details={
                "reachable": reachable,
                "latency_ms": latency,
                "packet_loss_percent": packet_loss,
            },
        ),
        findings,
    )


def _lte_signal_rating(
    rsrp: float | None,
) -> str:
    if rsrp is None:
        return "unknown"

    if rsrp >= -80:
        return "excellent"

    if rsrp >= -90:
        return "good"

    if rsrp >= -100:
        return "fair"

    if rsrp >= -110:
        return "weak"

    return "critical"


def _analyze_lte(
    collector: dict[str, Any],
) -> tuple[
    ComponentAnalysis,
    list[IntelligenceFinding],
]:
    lte = collector.get("lte") or {}
    findings: list[IntelligenceFinding] = []

    available = lte.get("available") is True

    if not available:
        findings.append(
            IntelligenceFinding(
                code="LTE_UNAVAILABLE",
                title="LTE metrics unavailable",
                severity=FindingSeverity.WARNING,
                message=(
                    "LTE modem metrics could not be read."
                ),
                recommendation=(
                    "Check the LTE RouterOS API account, "
                    "interface and network path."
                ),
            )
        )

        return (
            ComponentAnalysis(
                name="lte",
                available=False,
                score=25,
                health=HealthState.DEGRADED,
            ),
            findings,
        )

    running = lte.get("running") is True
    rsrp = _number(
        lte.get("rsrp_dbm", lte.get("rsrp"))
    )
    rsrq = _number(
        lte.get("rsrq_db", lte.get("rsrq"))
    )
    sinr = _number(
        lte.get("sinr_db", lte.get("sinr"))
    )
    rssi = _number(
        lte.get("rssi_dbm", lte.get("rssi"))
    )

    score = 100

    if not running:
        score = 0
        findings.append(
            IntelligenceFinding(
                code="LTE_NOT_RUNNING",
                title="LTE interface is not running",
                severity=FindingSeverity.CRITICAL,
                message=(
                    "The LTE modem interface is currently "
                    "not operational."
                ),
                metric="lte.running",
                value=False,
                threshold=True,
                recommendation=(
                    "Check SIM status, registration, modem "
                    "state and LTE interface configuration."
                ),
            )
        )
    else:
        if rsrp is not None:
            if rsrp < -110:
                score -= 45
                severity = FindingSeverity.CRITICAL
            elif rsrp < -100:
                score -= 30
                severity = FindingSeverity.HIGH
            elif rsrp < -90:
                score -= 15
                severity = FindingSeverity.WARNING
            elif rsrp < -80:
                score -= 5
                severity = FindingSeverity.NOTICE
            else:
                severity = None

            if severity is not None:
                findings.append(
                    IntelligenceFinding(
                        code="LTE_RSRP_LOW",
                        title="LTE signal power is low",
                        severity=severity,
                        message=f"RSRP is {rsrp:.0f} dBm.",
                        metric="lte.rsrp_dbm",
                        value=rsrp,
                        threshold=-90,
                        recommendation=(
                            "Check antenna alignment, "
                            "band selection and cell choice."
                        ),
                    )
                )

        if rsrq is not None:
            if rsrq < -20:
                score -= 35
                severity = FindingSeverity.CRITICAL
            elif rsrq < -15:
                score -= 25
                severity = FindingSeverity.HIGH
            elif rsrq < -12:
                score -= 15
                severity = FindingSeverity.WARNING
            elif rsrq < -10:
                score -= 5
                severity = FindingSeverity.NOTICE
            else:
                severity = None

            if severity is not None:
                findings.append(
                    IntelligenceFinding(
                        code="LTE_RSRQ_LOW",
                        title="LTE signal quality is degraded",
                        severity=severity,
                        message=f"RSRQ is {rsrq:.0f} dB.",
                        metric="lte.rsrq_db",
                        value=rsrq,
                        threshold=-12,
                        recommendation=(
                            "Check sector congestion, "
                            "interference and antenna position."
                        ),
                    )
                )

        if sinr is not None:
            if sinr < 0:
                score -= 45
                severity = FindingSeverity.CRITICAL
            elif sinr < 5:
                score -= 30
                severity = FindingSeverity.HIGH
            elif sinr < 10:
                score -= 15
                severity = FindingSeverity.WARNING
            elif sinr < 15:
                score -= 5
                severity = FindingSeverity.NOTICE
            else:
                severity = None

            if severity is not None:
                findings.append(
                    IntelligenceFinding(
                        code="LTE_SINR_LOW",
                        title="LTE interference level is high",
                        severity=severity,
                        message=f"SINR is {sinr:.0f} dB.",
                        metric="lte.sinr_db",
                        value=sinr,
                        threshold=10,
                        recommendation=(
                            "Evaluate another cell, band or "
                            "antenna orientation."
                        ),
                    )
                )

    score = max(0, score)

    return (
        ComponentAnalysis(
            name="lte",
            available=True,
            score=score,
            health=_health_from_score(score),
            details={
                "running": running,
                "operator": lte.get("operator"),
                "data_class": lte.get("data_class"),
                "primary_band": lte.get(
                    "primary_band"
                ),
                "cell_id": lte.get("cell_id"),
                "rsrp_dbm": rsrp,
                "rsrq_db": rsrq,
                "sinr_db": sinr,
                "rssi_dbm": rssi,
                "signal_quality":
                    _lte_signal_rating(rsrp),
            },
        ),
        findings,
    )


def analyze_network_intelligence(
    collector: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(collector, dict):
        raise TypeError(
            "collector must be a dictionary"
        )

    components: dict[str, ComponentAnalysis] = {}
    findings: list[IntelligenceFinding] = []

    for name, analyzer in (
        ("device", _analyze_device),
        ("traffic", _analyze_traffic),
        ("ping", _analyze_ping),
        ("lte", _analyze_lte),
    ):
        component, component_findings = analyzer(
            collector
        )

        components[name] = component
        findings.extend(component_findings)

    available_weight = sum(
        WEIGHTS[name]
        for name, component in components.items()
        if component.available
    )

    if available_weight <= 0:
        overall_score = 0
        confidence = 0
        overall_health = HealthState.UNAVAILABLE
    else:
        weighted_score = sum(
            components[name].score * WEIGHTS[name]
            for name in components
            if components[name].available
        )

        overall_score = round(
            weighted_score / available_weight
        )

        confidence = round(
            available_weight * 100
        )

        overall_health = _health_from_score(
            overall_score
        )

    severity_order = {
        FindingSeverity.CRITICAL: 6,
        FindingSeverity.HIGH: 5,
        FindingSeverity.WARNING: 4,
        FindingSeverity.NOTICE: 3,
        FindingSeverity.INFO: 2,
        FindingSeverity.HEALTHY: 1,
    }

    findings.sort(
        key=lambda item: severity_order[
            item.severity
        ],
        reverse=True,
    )

    finding_severities = {
        finding.severity
        for finding in findings
    }

    device_component = components.get("device")

    if (
        device_component is not None
        and device_component.details.get(
            "reachable"
        ) is False
    ):
        overall_health = HealthState.CRITICAL

    elif FindingSeverity.CRITICAL in finding_severities:
        overall_health = HealthState.CRITICAL

    elif FindingSeverity.HIGH in finding_severities:
        if overall_health in {
            HealthState.EXCELLENT,
            HealthState.HEALTHY,
        }:
            overall_health = HealthState.DEGRADED

    elif FindingSeverity.WARNING in finding_severities:
        if overall_health == HealthState.EXCELLENT:
            overall_health = HealthState.HEALTHY

    if confidence < 50:
        overall_health = HealthState.UNAVAILABLE

    elif confidence < 75:
        if overall_health in {
            HealthState.EXCELLENT,
            HealthState.HEALTHY,
        }:
            overall_health = HealthState.DEGRADED

    recommendations: list[str] = []

    for finding in findings:
        recommendation = finding.recommendation

        if (
            recommendation
            and recommendation not in recommendations
        ):
            recommendations.append(recommendation)

    analysis = NetworkIntelligenceAnalysis(
        overall_health_score=overall_score,
        overall_health=overall_health,
        confidence_percent=confidence,
        components=components,
        findings=findings,
        recommendations=recommendations,
        analyzer_name=ANALYZER_NAME,
        analyzer_version=ANALYZER_VERSION,
    )

    return analysis.to_dict()
