from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.models.noc_wall_dashboard import (
    DASHBOARD_SCHEMA_VERSION,
    NOCWallDashboardAlert,
    NOCWallDashboardSeverity,
    NOCWallDashboardSnapshot,
    NOCWallDashboardStatus,
    NOCWallDashboardTrend,
)


GENERATED_AT = datetime(
    2026,
    8,
    7,
    1,
    15,
    tzinfo=timezone.utc,
)


def make_alert(
    *,
    alert_id: str = "alert:1",
) -> NOCWallDashboardAlert:
    return NOCWallDashboardAlert(
        alert_id=alert_id,
        title="Critical link degradation",
        message="Backhaul link signal is degrading.",
        severity=(
            NOCWallDashboardSeverity.CRITICAL
        ),
        source="predictive-intelligence",
        created_at=GENERATED_AT,
        site_id="site:buqayq",
        link_id="link:uqair",
    )


def make_snapshot(
    **overrides,
) -> NOCWallDashboardSnapshot:
    values = {
        "dashboard_id":
            "noc-wall-dashboard:20260807T011500Z",
        "generated_at":
            GENERATED_AT,
        "overall_status":
            NOCWallDashboardStatus.DEGRADED,
        "overall_health_score":
            76.5,
        "overall_trend":
            NOCWallDashboardTrend.DEGRADING,
        "total_sites":
            4,
        "healthy_sites":
            2,
        "degraded_sites":
            1,
        "critical_sites":
            1,
        "unknown_sites":
            0,
        "total_devices":
            20,
        "online_devices":
            16,
        "offline_devices":
            2,
        "degraded_devices":
            2,
        "total_links":
            8,
        "healthy_links":
            5,
        "degraded_links":
            2,
        "down_links":
            1,
        "active_incidents":
            3,
        "critical_incidents":
            1,
        "high_priority_incidents":
            1,
        "active_predictions":
            4,
        "critical_predictions":
            1,
        "high_risk_predictions":
            2,
        "pending_human_approvals":
            2,
        "approved_but_not_executable":
            1,
        "latest_report_id":
            "executive-predictive-report:1",
        "latest_report_fingerprint":
            "a" * 64,
        "latest_report_health_score":
            76.5,
        "affected_sites":
            (
                "site:buqayq",
                "site:uqair",
            ),
        "affected_devices":
            (
                "device:af5xhd-1",
            ),
        "affected_links":
            (
                "link:uqair",
            ),
        "affected_services":
            (
                "internet-access",
            ),
        "alerts":
            (
                make_alert(),
            ),
        "source_audit_ids":
            (
                "audit:predictive",
                "audit:report",
            ),
        "source_record_hashes":
            (
                "b" * 64,
                "c" * 64,
            ),
        "metadata": {
            "environment":
                "production",
        },
    }

    values.update(
        overrides
    )

    return NOCWallDashboardSnapshot(
        **values
    )


def test_create_dashboard_snapshot() -> None:
    snapshot = make_snapshot()

    assert snapshot.overall_status is (
        NOCWallDashboardStatus.DEGRADED
    )

    assert snapshot.overall_health_score == 76.5
    assert snapshot.total_sites == 4
    assert snapshot.total_devices == 20
    assert snapshot.total_links == 8
    assert snapshot.active_predictions == 4
    assert snapshot.schema_version == (
        DASHBOARD_SCHEMA_VERSION
    )


def test_snapshot_is_immutable() -> None:
    snapshot = make_snapshot()

    with pytest.raises(
        FrozenInstanceError,
    ):
        snapshot.total_sites = 10


def test_alert_is_immutable() -> None:
    alert = make_alert()

    with pytest.raises(
        FrozenInstanceError,
    ):
        alert.title = "Changed"


def test_fingerprint_is_sha256() -> None:
    snapshot = make_snapshot()

    assert len(
        snapshot.dashboard_fingerprint
    ) == 64

    assert (
        snapshot.dashboard_fingerprint
        == snapshot.calculate_fingerprint()
    )


def test_fingerprint_is_deterministic() -> None:
    first = make_snapshot()
    second = make_snapshot()

    assert (
        first.dashboard_fingerprint
        == second.dashboard_fingerprint
    )


def test_tampered_fingerprint_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="fingerprint",
    ):
        make_snapshot(
            dashboard_fingerprint=(
                "f" * 64
            )
        )


def test_site_counters_must_match_total() -> None:
    with pytest.raises(
        ValueError,
        match="site counters",
    ):
        make_snapshot(
            total_sites=5
        )


def test_device_counters_must_match_total() -> None:
    with pytest.raises(
        ValueError,
        match="device counters",
    ):
        make_snapshot(
            total_devices=21
        )


def test_link_counters_must_match_total() -> None:
    with pytest.raises(
        ValueError,
        match="link counters",
    ):
        make_snapshot(
            total_links=9
        )


def test_incident_severity_cannot_exceed_total() -> None:
    with pytest.raises(
        ValueError,
        match="incident",
    ):
        make_snapshot(
            active_incidents=1,
            critical_incidents=1,
            high_priority_incidents=1,
        )


def test_prediction_severity_cannot_exceed_total() -> None:
    with pytest.raises(
        ValueError,
        match="prediction",
    ):
        make_snapshot(
            active_predictions=1,
            critical_predictions=1,
            high_risk_predictions=1,
        )


def test_health_score_range_validation() -> None:
    with pytest.raises(
        ValueError,
        match="health_score",
    ):
        make_snapshot(
            overall_health_score=101,
        )


def test_negative_counter_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="negative",
    ):
        make_snapshot(
            active_incidents=-1,
        )


def test_naive_generated_at_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        make_snapshot(
            generated_at=datetime(
                2026,
                8,
                7,
                1,
                15,
            )
        )


def test_duplicate_alert_ids_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        make_snapshot(
            alerts=(
                make_alert(
                    alert_id="alert:1"
                ),
                make_alert(
                    alert_id="alert:1"
                ),
            )
        )


def test_duplicate_sources_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        make_snapshot(
            source_audit_ids=(
                "audit:1",
                "audit:1",
            )
        )


def test_alert_to_dict() -> None:
    alert = make_alert()

    payload = alert.to_dict()

    assert payload["alert_id"] == "alert:1"
    assert payload["severity"] == "critical"
    assert payload["acknowledged"] is False


def test_snapshot_to_dict() -> None:
    snapshot = make_snapshot()

    payload = snapshot.to_dict()

    assert payload["dashboard_id"] == (
        snapshot.dashboard_id
    )

    assert payload["overall_status"] == (
        "degraded"
    )

    assert payload["alerts"][0]["alert_id"] == (
        "alert:1"
    )

    assert payload["can_execute"] is False


def test_snapshot_never_grants_execution() -> None:
    snapshot = make_snapshot()

    assert snapshot.incident_created is False
    assert snapshot.recommendation_executed is False
    assert snapshot.decision_created is False
    assert snapshot.authorization_created is False
    assert snapshot.execution_allowed is False
    assert snapshot.can_execute is False

    payload = snapshot.to_dict()

    assert (
        payload["safety"]["display_only"]
        is True
    )

    assert (
        payload["safety"]["read_only_snapshot"]
        is True
    )

    assert payload["can_execute"] is False


def test_invalid_status_type_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="overall_status",
    ):
        make_snapshot(
            overall_status="healthy"
        )


def test_invalid_alert_severity_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="severity",
    ):
        NOCWallDashboardAlert(
            alert_id="alert:1",
            title="Title",
            message="Message",
            severity="critical",
            source="test",
            created_at=GENERATED_AT,
        )
