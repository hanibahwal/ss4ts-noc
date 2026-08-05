from __future__ import annotations

from typing import Any


SERVICE_NAME = "SS4TS Executive Narrative Engine"
SERVICE_VERSION = "1.0.0"


STATUS_CONFIG = {
    "excellent": {
        "headline": "الشبكة تعمل بكفاءة ممتازة",
        "priority": "low",
        "requires_immediate_action": False,
    },
    "healthy": {
        "headline": "الشبكة تعمل بصورة جيدة",
        "priority": "low",
        "requires_immediate_action": False,
    },
    "degraded": {
        "headline": "الشبكة تعمل ولكنها تحتاج متابعة",
        "priority": "high",
        "requires_immediate_action": True,
    },
    "critical": {
        "headline": "الشبكة تواجه حالة حرجة",
        "priority": "critical",
        "requires_immediate_action": True,
    },
}


SEVERITY_ARABIC = {
    "critical": "حرجة",
    "high": "مرتفعة",
    "warning": "تحذيرية",
    "notice": "تنبيهية",
    "info": "معلوماتية",
}


FINDING_TITLES_ARABIC = {
    "DEVICE_UNREACHABLE": "تعذر الوصول إلى جهاز التوجيه",
    "DEVICE_HIGH_CPU": "ارتفاع استخدام المعالج",
    "DEVICE_HIGH_MEMORY": "ارتفاع استخدام الذاكرة",
    "DEVICE_HIGH_TEMPERATURE": "ارتفاع درجة حرارة الجهاز",
    "TRAFFIC_UNAVAILABLE": "بيانات حركة المرور غير متاحة",
    "TRAFFIC_HISTORY_MISSING": "السجل التاريخي لحركة المرور غير متاح",
    "TRAFFIC_RISING": "حركة المرور في ارتفاع",
    "PING_UNAVAILABLE": "بيانات الاتصال غير متاحة",
    "PING_UNREACHABLE": "الجهاز لا يستجيب لاختبار الاتصال",
    "PING_PACKET_LOSS": "فقدان حزم في الاتصال",
    "PING_HIGH_LATENCY": "ارتفاع زمن الاستجابة",
    "LTE_UNAVAILABLE": "بيانات LTE غير متاحة",
    "LTE_NOT_RUNNING": "اتصال LTE غير نشط",
    "LTE_RSRP_LOW": "ضعف مستوى إشارة LTE",
    "LTE_RSRQ_LOW": "انخفاض جودة إشارة LTE",
    "LTE_SINR_LOW": "وجود تداخل في إشارة LTE",
}


RECOMMENDATIONS_ARABIC = {
    "DEVICE_UNREACHABLE": (
        "فحص الطاقة والتوجيه واتصال VPN وإمكانية الوصول إلى RouterOS."
    ),
    "DEVICE_HIGH_CPU": (
        "مراجعة قواعد الجدار الناري والطوابير وتتبع الاتصالات "
        "وحجم الحمل على الجهاز."
    ),
    "DEVICE_HIGH_MEMORY": (
        "مراجعة الخدمات والجلسات النشطة واستهلاك موارد RouterOS."
    ),
    "DEVICE_HIGH_TEMPERATURE": (
        "فحص التهوية والتبريد ودرجة حرارة غرفة المعدات."
    ),
    "TRAFFIC_UNAVAILABLE": (
        "فحص جمع بيانات SNMP وقواعد اختيار الواجهة الرئيسية."
    ),
    "TRAFFIC_HISTORY_MISSING": (
        "فحص الاحتفاظ ببيانات حركة المرور واستعلامات InfluxDB."
    ),
    "TRAFFIC_RISING": (
        "الاستمرار في مراقبة السعة واستهلاك الواجهة."
    ),
    "PING_UNAVAILABLE": (
        "فحص خدمة Telegraf Ping واتصال InfluxDB."
    ),
    "PING_UNREACHABLE": (
        "فحص التوجيه والجدار الناري وتوفر الجهاز فورًا."
    ),
    "PING_PACKET_LOSS": (
        "فحص جودة الرابط والازدحام ومسار الاتصال."
    ),
    "PING_HIGH_LATENCY": (
        "فحص الازدحام ومسار الشبكة وزمن استجابة مزود الخدمة."
    ),
    "LTE_UNAVAILABLE": (
        "فحص واجهة LTE وخدمة جمع بيانات RouterOS."
    ),
    "LTE_NOT_RUNNING": (
        "فحص حالة الشريحة والتسجيل بالشبكة وإعدادات واجهة LTE."
    ),
    "LTE_RSRP_LOW": (
        "تحسين اتجاه الهوائي وفحص التغطية والمسافة من البرج."
    ),
    "LTE_RSRQ_LOW": (
        "فحص ازدحام القطاع والتداخل وموضع الهوائي."
    ),
    "LTE_SINR_LOW": (
        "فحص مصادر التداخل وإعادة توجيه الهوائي أو تغيير الخلية."
    ),
}


def _safe_number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _arabic_status(status: str) -> str:
    return {
        "excellent": "ممتازة",
        "healthy": "جيدة",
        "degraded": "متدهورة جزئيًا",
        "critical": "حرجة",
    }.get(status, "غير معروفة")


def _priority_from_findings(
    status: str,
    findings: list[dict[str, Any]],
) -> tuple[str, bool]:
    severities = {
        str(item.get("severity", "")).lower()
        for item in findings
    }

    if "critical" in severities:
        return "critical", True

    if "high" in severities:
        return "high", True

    if status in {"critical", "degraded"}:
        return STATUS_CONFIG.get(
            status,
            STATUS_CONFIG["degraded"],
        )["priority"], True

    if "warning" in severities:
        return "medium", False

    return "low", False


def _build_observation(
    finding: dict[str, Any],
) -> dict[str, Any]:
    code = str(
        finding.get("code") or "UNKNOWN"
    )

    severity = str(
        finding.get("severity") or "info"
    ).lower()

    title = FINDING_TITLES_ARABIC.get(
        code,
        str(finding.get("title") or code),
    )

    recommendation = RECOMMENDATIONS_ARABIC.get(
        code,
        str(
            finding.get("recommendation")
            or "الاستمرار في المراقبة."
        ),
    )

    return {
        "code": code,
        "title": title,
        "severity": severity,
        "severity_ar": SEVERITY_ARABIC.get(
            severity,
            severity,
        ),
        "value": finding.get("value"),
        "metric": finding.get("metric"),
        "recommendation": recommendation,
    }


def build_executive_narrative(
    intelligence: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert Network Intelligence output into an
    Arabic executive narrative.

    The engine is deterministic and does not depend
    on an external language model.
    """

    status = str(
        intelligence.get("status") or "unknown"
    ).lower()

    health_score = int(
        round(
            _safe_number(
                intelligence.get("health_score")
            )
        )
    )

    confidence = int(
        round(
            _safe_number(
                intelligence.get(
                    "confidence_percent"
                )
            )
        )
    )

    collector = (
        intelligence.get("collector")
        or {}
    )

    analysis = (
        intelligence.get("analysis")
        or {}
    )

    summary = (
        collector.get("summary")
        or {}
    )

    device = (
        collector.get("device")
        or {}
    )

    traffic = (
        collector.get("traffic")
        or {}
    )

    ping = (
        collector.get("ping")
        or {}
    )

    lte = (
        collector.get("lte")
        or {}
    )

    findings = [
        item
        for item in (
            analysis.get("findings")
            or []
        )
        if isinstance(item, dict)
    ]

    observations = [
        _build_observation(item)
        for item in findings
    ]

    priority, immediate_action = (
        _priority_from_findings(
            status,
            findings,
        )
    )

    config = STATUS_CONFIG.get(
        status,
        {
            "headline": (
                "حالة الشبكة غير مكتملة"
            ),
            "priority": priority,
            "requires_immediate_action": (
                immediate_action
            ),
        },
    )

    available_sources = int(
        _safe_number(
            summary.get("available_sources")
        )
    )

    total_sources = int(
        _safe_number(
            summary.get("total_sources")
        )
    )

    selected_interface = (
        summary.get("selected_interface")
        or traffic.get("selected_interface")
        or "غير محددة"
    )

    identity = (
        device.get("identity")
        or intelligence.get("router_ip")
        or "الجهاز الرئيسي"
    )

    cpu = _safe_number(
        device.get("cpu_usage_percent")
    )

    memory = _safe_number(
        device.get("memory_usage_percent")
    )

    latency = _safe_number(
        ping.get("latency_ms")
    )

    packet_loss = _safe_number(
        ping.get("packet_loss_percent")
    )

    status_ar = _arabic_status(status)

    executive_summary = (
        f"حالة الشبكة الحالية {status_ar} "
        f"بدرجة صحة {health_score} من 100. "
        f"تم تحليل {available_sources} من أصل "
        f"{total_sources} مصادر بيانات، "
        f"وبمستوى ثقة {confidence}%."
    )

    operational_summary = (
        f"الجهاز الرئيسي {identity} متصل، "
        f"والواجهة الأساسية المستخدمة هي "
        f"{selected_interface}. "
        f"استخدام المعالج {cpu:.0f}%، "
        f"واستخدام الذاكرة {memory:.0f}%. "
        f"زمن الاستجابة {latency:.1f} مللي ثانية، "
        f"ونسبة فقدان الحزم {packet_loss:.1f}%."
    )

    critical_count = sum(
        1
        for item in observations
        if item["severity"] == "critical"
    )

    high_count = sum(
        1
        for item in observations
        if item["severity"] == "high"
    )

    warning_count = sum(
        1
        for item in observations
        if item["severity"] == "warning"
    )

    if critical_count:
        business_impact = (
            f"يوجد {critical_count} مؤشر حرج "
            "قد يؤدي إلى انقطاع أو تدهور واضح "
            "في الخدمة ويتطلب تدخلًا فوريًا."
        )
    elif high_count:
        business_impact = (
            f"يوجد {high_count} مؤشر مرتفع الخطورة "
            "قد يؤثر في استقرار الشبكة أو جودة الخدمة."
        )
    elif warning_count:
        business_impact = (
            f"لا يوجد انقطاع حالي، لكن يوجد "
            f"{warning_count} تحذير يحتاج إلى متابعة "
            "لمنع تطوره إلى مشكلة تشغيلية."
        )
    else:
        business_impact = (
            "لا توجد مؤشرات حالية على تأثير تشغيلي "
            "أو انقطاع في الخدمة."
        )

    if not observations:
        recommended_actions = [
            "الاستمرار في المراقبة الدورية.",
            "مراجعة مؤشرات الأداء عند حدوث تغير في درجة الصحة.",
        ]
    else:
        recommended_actions = []

        for item in observations:
            action = item["recommendation"]

            if action not in recommended_actions:
                recommended_actions.append(
                    action
                )

    lte_summary = {
        "available": lte.get("available") is True,
        "operator": lte.get("operator"),
        "data_class": lte.get("data_class"),
        "rsrp_dbm": lte.get("rsrp_dbm"),
        "rsrq_db": lte.get("rsrq_db"),
        "sinr_db": lte.get("sinr_db"),
    }

    return {
        "router_ip": intelligence.get(
            "router_ip"
        ),
        "generated_at": intelligence.get(
            "generated_at"
        ),
        "status": status,
        "status_ar": status_ar,
        "health_score": health_score,
        "confidence_percent": confidence,
        "headline": config["headline"],
        "executive_summary": executive_summary,
        "operational_summary": operational_summary,
        "business_impact": business_impact,
        "priority": priority,
        "requires_immediate_action": (
            immediate_action
        ),
        "key_observations": observations,
        "recommended_actions": (
            recommended_actions
        ),
        "metrics": {
            "available_sources": (
                available_sources
            ),
            "total_sources": total_sources,
            "selected_interface": (
                selected_interface
            ),
            "cpu_usage_percent": cpu,
            "memory_usage_percent": memory,
            "latency_ms": latency,
            "packet_loss_percent": (
                packet_loss
            ),
        },
        "lte_summary": lte_summary,
        "engine": {
            "name": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "mode": "deterministic",
            "language": "ar",
        },
    }
