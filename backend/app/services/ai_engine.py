from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


MAX_SCORE = 100


SEVERITY_WEIGHT = {
    "critical": 5,
    "high": 4,
    "warning": 3,
    "medium": 2,
    "notice": 1,
    "info": 0,
    "healthy": 0,
}


CATEGORY_LABELS = {
    "connectivity": "الاتصال",
    "cpu": "المعالج",
    "memory": "الذاكرة",
    "interfaces": "الواجهات",
    "errors": "الأخطاء",
    "utilization": "الاستخدام",
    "traffic": "حركة الشبكة",
    "availability": "التوفر",
}


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default

    if numeric_value != numeric_value:
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


def _normalize_interface(
    item: dict[str, Any],
) -> dict[str, Any]:
    rx_bps = _number(
        item.get("rx_bps"),
    )

    tx_bps = _number(
        item.get("tx_bps"),
    )

    total_bps = _number(
        item.get("total_bps"),
        rx_bps + tx_bps,
    )

    speed_bps = _number(
        item.get("speed_bps"),
    )

    utilization = item.get(
        "utilization_percent"
    )

    if utilization is None:
        utilization_percent = None
    else:
        utilization_percent = _clamp(
            _number(utilization),
        )

    rx_errors = _integer(
        item.get("rx_errors"),
    )

    tx_errors = _integer(
        item.get("tx_errors"),
    )

    total_errors = _integer(
        item.get("total_errors"),
        rx_errors + tx_errors,
    )

    admin_status = str(
        item.get("admin_status")
        or "unknown"
    ).lower()

    oper_status = str(
        item.get("oper_status")
        or "unknown"
    ).lower()

    is_admin_up = bool(
        item.get(
            "is_admin_up",
            admin_status == "up",
        )
    )

    is_oper_up = bool(
        item.get(
            "is_oper_up",
            oper_status == "up",
        )
    )

    return {
        **item,
        "if_descr": (
            item.get("if_descr")
            or item.get("name")
            or "unknown"
        ),
        "if_index": item.get("if_index"),
        "if_type": (
            item.get("if_type")
            or "unknown"
        ),
        "admin_status": admin_status,
        "oper_status": oper_status,
        "is_admin_up": is_admin_up,
        "is_oper_up": is_oper_up,
        "speed_bps": speed_bps,
        "rx_bps": rx_bps,
        "tx_bps": tx_bps,
        "total_bps": total_bps,
        "utilization_percent":
            utilization_percent,
        "rx_errors": rx_errors,
        "tx_errors": tx_errors,
        "total_errors": total_errors,
        "has_errors": bool(
            item.get("has_errors")
            or total_errors > 0
        ),
        "mtu": _integer(
            item.get("mtu"),
        ),
    }


def _create_issue(
    *,
    issue_id: str,
    severity: str,
    category: str,
    title: str,
    description: str,
    confidence: int,
    score_penalty: int,
    recommendation: str = "",
    interface_name: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "severity": severity,
        "category": category,
        "category_label":
            CATEGORY_LABELS.get(
                category,
                category,
            ),
        "title": title,
        "description": description,
        "confidence": int(
            _clamp(confidence),
        ),
        "score_penalty": max(
            0,
            int(score_penalty),
        ),
        "recommendation":
            recommendation,
        "interface_name":
            interface_name,
        "evidence": evidence or {},
    }


def _analyze_connectivity(
    *,
    is_online: bool,
    interfaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    if not is_online:
        issues.append(
            _create_issue(
                issue_id="device-offline",
                severity="critical",
                category="connectivity",
                title="الجهاز غير متصل",
                description=(
                    "تعذر الوصول إلى الجهاز أو "
                    "لم يتم استلام استجابة حديثة."
                ),
                confidence=99,
                score_penalty=30,
                recommendation=(
                    "تحقق من الطاقة، الربط، المسار، "
                    "SNMP وMikroTik API."
                ),
            )
        )

        return issues

    operational_interfaces = [
        item
        for item in interfaces
        if item["is_oper_up"]
    ]

    if (
        interfaces
        and not operational_interfaces
    ):
        issues.append(
            _create_issue(
                issue_id="no-operational-interfaces",
                severity="critical",
                category="connectivity",
                title="لا توجد واجهة تشغيلية",
                description=(
                    "الجهاز يستجيب، لكن جميع "
                    "الواجهات في حالة توقف."
                ),
                confidence=96,
                score_penalty=20,
                recommendation=(
                    "تحقق من الكوابل والطرف المقابل "
                    "وPoE وSFP وحالة الرابط."
                ),
            )
        )

    return issues


def _analyze_cpu(
    cpu_usage: float | None,
) -> list[dict[str, Any]]:
    if cpu_usage is None:
        return []

    cpu = _clamp(
        _number(cpu_usage),
    )

    if cpu >= 95:
        return [
            _create_issue(
                issue_id="cpu-critical",
                severity="critical",
                category="cpu",
                title=(
                    "استخدام المعالج في مستوى حرج"
                ),
                description=(
                    f"وصل استخدام CPU إلى "
                    f"{cpu:.1f}%."
                ),
                confidence=98,
                score_penalty=20,
                recommendation=(
                    "افحص Connection Tracking، "
                    "Firewall، Queues، Scripts "
                    "والاتصالات النشطة."
                ),
                evidence={
                    "cpu_usage": cpu,
                },
            )
        ]

    if cpu >= 85:
        return [
            _create_issue(
                issue_id="cpu-high",
                severity="high",
                category="cpu",
                title="استخدام المعالج مرتفع",
                description=(
                    f"استخدام CPU الحالي "
                    f"{cpu:.1f}%."
                ),
                confidence=95,
                score_penalty=14,
                recommendation=(
                    "راقب الحمل لمدة 10 دقائق "
                    "وافحص Firewall وQueues "
                    "والارتفاعات المفاجئة في الحركة."
                ),
                evidence={
                    "cpu_usage": cpu,
                },
            )
        ]

    if cpu >= 70:
        return [
            _create_issue(
                issue_id="cpu-elevated",
                severity="notice",
                category="cpu",
                title=(
                    "استخدام المعالج مرتفع نسبيًا"
                ),
                description=(
                    f"استخدام CPU الحالي "
                    f"{cpu:.1f}%."
                ),
                confidence=90,
                score_penalty=6,
                recommendation=(
                    "لا يوجد إجراء عاجل، "
                    "لكن يوصى بمتابعة اتجاه الحمل."
                ),
                evidence={
                    "cpu_usage": cpu,
                },
            )
        ]

    return []


def _analyze_memory(
    memory_usage: float | None,
) -> list[dict[str, Any]]:
    if memory_usage is None:
        return []

    memory = _clamp(
        _number(memory_usage),
    )

    if memory >= 95:
        return [
            _create_issue(
                issue_id="memory-critical",
                severity="critical",
                category="memory",
                title=(
                    "استخدام الذاكرة في مستوى حرج"
                ),
                description=(
                    f"وصل استخدام الذاكرة إلى "
                    f"{memory:.1f}%."
                ),
                confidence=98,
                score_penalty=15,
                recommendation=(
                    "افحص الذاكرة الحرة وعدد "
                    "الاتصالات والخدمات والعمليات."
                ),
                evidence={
                    "memory_usage": memory,
                },
            )
        ]

    if memory >= 85:
        return [
            _create_issue(
                issue_id="memory-high",
                severity="high",
                category="memory",
                title="استخدام الذاكرة مرتفع",
                description=(
                    f"استخدام الذاكرة الحالي "
                    f"{memory:.1f}%."
                ),
                confidence=95,
                score_penalty=10,
                recommendation=(
                    "راقب Free Memory وعدد "
                    "الاتصالات والخدمات النشطة."
                ),
                evidence={
                    "memory_usage": memory,
                },
            )
        ]

    if memory >= 75:
        return [
            _create_issue(
                issue_id="memory-elevated",
                severity="notice",
                category="memory",
                title=(
                    "استخدام الذاكرة مرتفع نسبيًا"
                ),
                description=(
                    f"استخدام الذاكرة الحالي "
                    f"{memory:.1f}%."
                ),
                confidence=90,
                score_penalty=5,
                recommendation=(
                    "لا يوجد إجراء عاجل، "
                    "لكن يوصى بمتابعة الاتجاه."
                ),
                evidence={
                    "memory_usage": memory,
                },
            )
        ]

    return []


def _analyze_interface_states(
    interfaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    if not interfaces:
        issues.append(
            _create_issue(
                issue_id="interfaces-unavailable",
                severity="warning",
                category="interfaces",
                title=(
                    "بيانات الواجهات غير متوفرة"
                ),
                description=(
                    "لا توجد بيانات كافية لتحليل "
                    "حالة واجهات الجهاز."
                ),
                confidence=95,
                score_penalty=10,
                recommendation=(
                    "تحقق من SNMP وTelegraf "
                    "وInfluxDB."
                ),
            )
        )

        return issues

    admin_up_oper_down = [
        item
        for item in interfaces
        if (
            item["is_admin_up"]
            and not item["is_oper_up"]
        )
    ]

    if admin_up_oper_down:
        count = len(
            admin_up_oper_down
        )

        penalty = min(
            10,
            count * 2,
        )

        issues.append(
            _create_issue(
                issue_id=(
                    "interfaces-admin-up-oper-down"
                ),
                severity=(
                    "high"
                    if count >= 5
                    else "warning"
                ),
                category="interfaces",
                title=(
                    "واجهات مفعلة إداريًا "
                    "لكنها متوقفة تشغيليًا"
                ),
                description=(
                    f"تم اكتشاف {count} واجهة "
                    "في حالة Admin Up / Oper Down."
                ),
                confidence=96,
                score_penalty=penalty,
                recommendation=(
                    "تحقق من الكابل والطرف المقابل "
                    "وPoE وSFP وحالة الرابط."
                ),
                evidence={
                    "count": count,
                    "interfaces": [
                        item["if_descr"]
                        for item
                        in admin_up_oper_down
                    ],
                },
            )
        )

    return issues


def _analyze_interface_errors(
    interfaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    for item in interfaces:
        total_errors = item[
            "total_errors"
        ]

        if total_errors <= 0:
            continue

        if total_errors >= 100:
            severity = "critical"
            penalty = 15
        elif total_errors >= 20:
            severity = "high"
            penalty = 10
        elif total_errors >= 5:
            severity = "warning"
            penalty = 6
        else:
            severity = "notice"
            penalty = 3

        interface_name = item[
            "if_descr"
        ]

        issues.append(
            _create_issue(
                issue_id=(
                    f"errors-{interface_name}"
                ),
                severity=severity,
                category="errors",
                title=(
                    f"أخطاء على {interface_name}"
                ),
                description=(
                    f"RX Errors: "
                    f"{item['rx_errors']} — "
                    f"TX Errors: "
                    f"{item['tx_errors']}."
                ),
                confidence=99,
                score_penalty=penalty,
                recommendation=(
                    "تحقق من الكابل وجودة الرابط "
                    "وDuplex وMTU والطرف المقابل."
                ),
                interface_name=
                    interface_name,
                evidence={
                    "rx_errors":
                        item["rx_errors"],
                    "tx_errors":
                        item["tx_errors"],
                    "total_errors":
                        total_errors,
                },
            )
        )

    return issues


def _analyze_utilization(
    interfaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    for item in interfaces:
        utilization = item[
            "utilization_percent"
        ]

        if utilization is None:
            continue

        interface_name = item[
            "if_descr"
        ]

        if utilization >= 90:
            issues.append(
                _create_issue(
                    issue_id=(
                        "utilization-critical-"
                        f"{interface_name}"
                    ),
                    severity="critical",
                    category="utilization",
                    title=(
                        "ازدحام حرج على "
                        f"{interface_name}"
                    ),
                    description=(
                        f"وصل استخدام الواجهة إلى "
                        f"{utilization:.2f}%."
                    ),
                    confidence=98,
                    score_penalty=10,
                    recommendation=(
                        "افحص Top Talkers وQueues "
                        "وفكر في رفع السعة أو "
                        "توزيع الحركة."
                    ),
                    interface_name=
                        interface_name,
                    evidence={
                        "utilization_percent":
                            utilization,
                        "rx_bps":
                            item["rx_bps"],
                        "tx_bps":
                            item["tx_bps"],
                        "speed_bps":
                            item["speed_bps"],
                    },
                )
            )

        elif utilization >= 75:
            issues.append(
                _create_issue(
                    issue_id=(
                        "utilization-warning-"
                        f"{interface_name}"
                    ),
                    severity="warning",
                    category="utilization",
                    title=(
                        "استخدام مرتفع على "
                        f"{interface_name}"
                    ),
                    description=(
                        f"وصل استخدام الواجهة إلى "
                        f"{utilization:.2f}%."
                    ),
                    confidence=95,
                    score_penalty=5,
                    recommendation=(
                        "راقب الاتجاه خلال ساعات "
                        "الذروة وافحص توزيع الحركة."
                    ),
                    interface_name=
                        interface_name,
                    evidence={
                        "utilization_percent":
                            utilization,
                    },
                )
            )

    return issues


def _build_root_causes(
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    root_causes: list[
        dict[str, Any]
    ] = []

    for issue in issues:
        if issue["severity"] not in {
            "critical",
            "high",
            "warning",
        }:
            continue

        cause = {
            "id": (
                f"root-cause-"
                f"{issue['id']}"
            ),
            "title": issue["title"],
            "description":
                issue["description"],
            "category":
                issue["category"],
            "severity":
                issue["severity"],
            "confidence":
                issue["confidence"],
            "interface_name":
                issue["interface_name"],
            "evidence":
                issue["evidence"],
        }

        root_causes.append(cause)

    root_causes.sort(
        key=lambda item: (
            SEVERITY_WEIGHT.get(
                item["severity"],
                0,
            ),
            item["confidence"],
        ),
        reverse=True,
    )

    return root_causes[:5]


def _build_recommendations(
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recommendations: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    sorted_issues = sorted(
        issues,
        key=lambda item: (
            SEVERITY_WEIGHT.get(
                item["severity"],
                0,
            ),
            item["confidence"],
        ),
        reverse=True,
    )

    for issue in sorted_issues:
        recommendation = str(
            issue.get(
                "recommendation"
            )
            or ""
        ).strip()

        if not recommendation:
            continue

        unique_key = (
            recommendation.lower()
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)

        recommendations.append(
            {
                "id": (
                    f"recommendation-"
                    f"{issue['id']}"
                ),
                "priority": (
                    "urgent"
                    if issue["severity"]
                    == "critical"
                    else "high"
                    if issue["severity"]
                    == "high"
                    else "medium"
                    if issue["severity"]
                    == "warning"
                    else "low"
                ),
                "title": issue["title"],
                "action": recommendation,
                "category":
                    issue["category"],
                "interface_name":
                    issue[
                        "interface_name"
                    ],
                "confidence":
                    issue["confidence"],
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "id": (
                    "recommendation-monitor"
                ),
                "priority": "low",
                "title": (
                    "لا توجد إجراءات عاجلة"
                ),
                "action": (
                    "استمر في المراقبة الدورية، "
                    "ولا توجد توصية تصحيحية حالية."
                ),
                "category": "availability",
                "interface_name": None,
                "confidence": 95,
            }
        )

    return recommendations[:8]


def _calculate_score(
    issues: list[dict[str, Any]],
) -> tuple[int, int]:
    total_penalty = sum(
        _integer(
            issue.get(
                "score_penalty"
            )
        )
        for issue in issues
    )

    total_penalty = min(
        MAX_SCORE,
        total_penalty,
    )

    score = max(
        0,
        MAX_SCORE - total_penalty,
    )

    return score, total_penalty


def _resolve_risk(
    *,
    score: int,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    critical_count = sum(
        1
        for item in issues
        if item["severity"]
        == "critical"
    )

    high_count = sum(
        1
        for item in issues
        if item["severity"]
        == "high"
    )

    warning_count = sum(
        1
        for item in issues
        if item["severity"]
        == "warning"
    )

    if (
        critical_count > 0
        or score < 50
    ):
        level = "critical"
        label = "حرج"
        color = "red"
    elif (
        high_count > 0
        or score < 70
    ):
        level = "high"
        label = "مرتفع"
        color = "orange"
    elif (
        warning_count > 0
        or score < 85
    ):
        level = "medium"
        label = "متوسط"
        color = "yellow"
    else:
        level = "low"
        label = "منخفض"
        color = "green"

    return {
        "level": level,
        "label": label,
        "color": color,
        "critical_count":
            critical_count,
        "high_count": high_count,
        "warning_count":
            warning_count,
    }


def _build_summary(
    *,
    score: int,
    risk: dict[str, Any],
    issues: list[dict[str, Any]],
    root_causes: list[dict[str, Any]],
    recommendations:
        list[dict[str, Any]],
) -> str:
    if not issues:
        return (
            "صحة الجهاز ممتازة، ولا توجد "
            "مشاكل تشغيلية مؤثرة حاليًا. "
            "يوصى بالاستمرار في المراقبة "
            "الدورية."
        )

    first_cause = (
        root_causes[0]
        if root_causes
        else None
    )

    first_recommendation = (
        recommendations[0]
        if recommendations
        else None
    )

    parts = [
        (
            f"درجة صحة الجهاز الحالية "
            f"{score} من 100، "
            f"ومستوى الخطر "
            f"{risk['label']}."
        )
    ]

    if first_cause:
        parts.append(
            "أهم سبب محتمل هو: "
            f"{first_cause['title']}."
        )

    if first_recommendation:
        parts.append(
            "الإجراء المقترح: "
            f"{first_recommendation['action']}"
        )

    return " ".join(parts)


def analyze_device(
    *,
    router_ip: str,
    is_online: bool,
    cpu_usage: float | None = None,
    memory_usage: float | None = None,
    interfaces: list[
        dict[str, Any]
    ] | None = None,
    device_name: str | None = None,
) -> dict[str, Any]:
    normalized_interfaces = [
        _normalize_interface(item)
        for item in (
            interfaces or []
        )
        if isinstance(item, dict)
    ]

    issues: list[
        dict[str, Any]
    ] = []

    issues.extend(
        _analyze_connectivity(
            is_online=is_online,
            interfaces=
                normalized_interfaces,
        )
    )

    issues.extend(
        _analyze_cpu(
            cpu_usage,
        )
    )

    issues.extend(
        _analyze_memory(
            memory_usage,
        )
    )

    issues.extend(
        _analyze_interface_states(
            normalized_interfaces,
        )
    )

    issues.extend(
        _analyze_interface_errors(
            normalized_interfaces,
        )
    )

    issues.extend(
        _analyze_utilization(
            normalized_interfaces,
        )
    )

    issues.sort(
        key=lambda item: (
            SEVERITY_WEIGHT.get(
                item["severity"],
                0,
            ),
            item["score_penalty"],
            item["confidence"],
        ),
        reverse=True,
    )

    score, total_penalty = (
        _calculate_score(issues)
    )

    risk = _resolve_risk(
        score=score,
        issues=issues,
    )

    root_causes = (
        _build_root_causes(
            issues,
        )
    )

    recommendations = (
        _build_recommendations(
            issues,
        )
    )

    summary = _build_summary(
        score=score,
        risk=risk,
        issues=issues,
        root_causes=root_causes,
        recommendations=
            recommendations,
    )

    operational_interfaces = sum(
        1
        for item
        in normalized_interfaces
        if item["is_oper_up"]
    )

    interfaces_with_errors = sum(
        1
        for item
        in normalized_interfaces
        if item["has_errors"]
    )

    high_utilization = sum(
        1
        for item
        in normalized_interfaces
        if (
            item[
                "utilization_percent"
            ]
            is not None
            and item[
                "utilization_percent"
            ] >= 75
        )
    )

    return {
        "router_ip": router_ip,
        "device_name":
            device_name
            or router_ip,
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "engine": {
            "name": (
                "SS4TS AI Network Engine"
            ),
            "version": "1.5.1",
            "mode": (
                "explainable-rule-based"
            ),
        },

        "health_score": score,
        "maximum_score":
            MAX_SCORE,
        "total_penalty":
            total_penalty,

        "risk": risk,

        "summary": summary,

        "root_causes":
            root_causes,

        "recommendations":
            recommendations,

        "issues": issues,

        "statistics": {
            "total_interfaces":
                len(
                    normalized_interfaces
                ),
            "operational_interfaces":
                operational_interfaces,
            "down_interfaces": (
                len(
                    normalized_interfaces
                )
                -
                operational_interfaces
            ),
            "interfaces_with_errors":
                interfaces_with_errors,
            "high_utilization_interfaces":
                high_utilization,
            "issue_count":
                len(issues),
            "root_cause_count":
                len(root_causes),
            "recommendation_count":
                len(recommendations),
        },

        "input_snapshot": {
            "is_online":
                bool(is_online),
            "cpu_usage":
                cpu_usage,
            "memory_usage":
                memory_usage,
        },
    }
