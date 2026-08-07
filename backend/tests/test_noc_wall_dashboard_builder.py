from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from app.models.noc_wall_dashboard import (
    NOCWallDashboardSeverity,
    NOCWallDashboardSnapshot,
    NOCWallDashboardStatus,
    NOCWallDashboardTrend,
)
from app.services.executive_predictive_report_store import (
    ExecutivePredictiveReportStore,
)
from app.services.noc_wall_dashboard_builder import (
    BUILDER_SERVICE_NAME,
    NOCWallDashboardBuilder,
    NOCWallDashboardOperationalState,
    build_noc_wall_dashboard_snapshot,
)
from tests.test_executive_predictive_report_store import (
    STORED_AT,
    append_report,
)


GENERATED_AT = (
    STORED_AT
    + timedelta(
        minutes=20
    )
)


def make_operational_state(
    **overrides,
) -> NOCWallDashboardOperationalState:
    values = {
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
        "pending_human_approvals":
            2,
        "approved_but_not_executable":
            1,
        "affected_sites":
            (
                "site:operational",
            ),
        "affected_devices":
            (
                "device:operational",
            ),
        "affected_links":
            (
                "link:operational",
            ),
        "affected_services":
            (
                "service:operational",
            ),
        "metadata": {
            "environment":
                "test",
        },
    }

    values.update(
        overrides
    )

    return NOCWallDashboardOperationalState(
        **values
    )


def make_report_store(
    tmp_path,
    *,
    with_report: bool = True,
):
    if with_report:
        record, store, *_ = append_report(
            tmp_path
        )

        return store, record

    store = ExecutivePredictiveReportStore(
        tmp_path
        / "reports.db"
    )

    return store, None


def build_snapshot(
    tmp_path,
    *,
    state=None,
    with_report: bool = True,
):
    store, record = make_report_store(
        tmp_path,
        with_report=with_report,
    )

    operational_state = (
        state
        or make_operational_state()
    )

    snapshot = (
        build_noc_wall_dashboard_snapshot(
            report_store=store,
            operational_state=(
                operational_state
            ),
            generated_at=GENERATED_AT,
            metadata={
                "display":
                    "main-wall",
            },
        )
    )

    return (
        snapshot,
        store,
        record,
        operational_state,
    )


def test_build_dashboard_snapshot(
    tmp_path,
) -> None:
    snapshot, _, record, state = (
        build_snapshot(
            tmp_path
        )
    )

    assert isinstance(
        snapshot,
        NOCWallDashboardSnapshot,
    )

    assert snapshot.total_sites == (
        state.total_sites
    )

    assert snapshot.total_devices == (
        state.total_devices
    )

    assert snapshot.total_links == (
        state.total_links
    )

    assert snapshot.latest_report_id == (
        record.report_id
    )

    assert snapshot.active_predictions == (
        record.prediction_count
    )


def test_builder_binds_report_fingerprint(
    tmp_path,
) -> None:
    snapshot, _, record, _ = (
        build_snapshot(
            tmp_path
        )
    )

    assert (
        snapshot.latest_report_fingerprint
        == record.report_fingerprint
    )

    assert (
        record.record_hash
        in snapshot.source_record_hashes
    )


def test_builder_binds_report_audit(
    tmp_path,
) -> None:
    snapshot, *_ = build_snapshot(
        tmp_path
    )

    assert len(
        snapshot.source_audit_ids
    ) == 1

    assert (
        snapshot.metadata[
            "report_store_audit_valid"
        ]
        is True
    )


def test_critical_state_produces_critical_status(
    tmp_path,
) -> None:
    snapshot, *_ = build_snapshot(
        tmp_path
    )

    assert snapshot.overall_status is (
        NOCWallDashboardStatus.CRITICAL
    )


def test_healthy_state_without_report(
    tmp_path,
) -> None:
    state = make_operational_state(
        total_sites=2,
        healthy_sites=2,
        degraded_sites=0,
        critical_sites=0,
        unknown_sites=0,
        total_devices=10,
        online_devices=10,
        offline_devices=0,
        degraded_devices=0,
        total_links=4,
        healthy_links=4,
        degraded_links=0,
        down_links=0,
        active_incidents=0,
        critical_incidents=0,
        high_priority_incidents=0,
        pending_human_approvals=0,
        approved_but_not_executable=0,
    )

    snapshot, _, record, _ = (
        build_snapshot(
            tmp_path,
            state=state,
            with_report=False,
        )
    )

    assert record is None

    assert snapshot.overall_status is (
        NOCWallDashboardStatus.HEALTHY
    )

    assert snapshot.overall_trend is (
        NOCWallDashboardTrend.STABLE
    )

    assert snapshot.overall_health_score == (
        100.0
    )

    assert snapshot.active_predictions == 0
    assert snapshot.latest_report_id is None
    assert snapshot.source_record_hashes == ()


def test_empty_state_is_unknown(
    tmp_path,
) -> None:
    state = make_operational_state(
        total_sites=0,
        healthy_sites=0,
        degraded_sites=0,
        critical_sites=0,
        unknown_sites=0,
        total_devices=0,
        online_devices=0,
        offline_devices=0,
        degraded_devices=0,
        total_links=0,
        healthy_links=0,
        degraded_links=0,
        down_links=0,
        active_incidents=0,
        critical_incidents=0,
        high_priority_incidents=0,
        pending_human_approvals=0,
        approved_but_not_executable=0,
    )

    snapshot, *_ = build_snapshot(
        tmp_path,
        state=state,
        with_report=False,
    )

    assert snapshot.overall_status is (
        NOCWallDashboardStatus.UNKNOWN
    )

    assert snapshot.overall_trend is (
        NOCWallDashboardTrend.UNKNOWN
    )


def test_builder_generates_alerts(
    tmp_path,
) -> None:
    snapshot, *_ = build_snapshot(
        tmp_path
    )

    alert_ids = {
        alert.alert_id
        for alert in snapshot.alerts
    }

    assert (
        "dashboard-alert:critical-sites"
        in alert_ids
    )

    assert (
        "dashboard-alert:down-links"
        in alert_ids
    )

    assert (
        "dashboard-alert:offline-devices"
        in alert_ids
    )

    assert (
        "dashboard-alert:critical-incidents"
        in alert_ids
    )

    assert (
        "dashboard-alert:pending-approvals"
        in alert_ids
    )


def test_critical_alerts_are_first(
    tmp_path,
) -> None:
    snapshot, *_ = build_snapshot(
        tmp_path
    )

    severities = tuple(
        alert.severity
        for alert in snapshot.alerts
    )

    first_non_critical = next(
        (
            index
            for index, severity
            in enumerate(
                severities
            )
            if severity
            is not NOCWallDashboardSeverity.CRITICAL
        ),
        len(
            severities
        ),
    )

    assert all(
        severity
        is NOCWallDashboardSeverity.CRITICAL
        for severity
        in severities[
            :first_non_critical
        ]
    )


def test_affected_entities_are_merged(
    tmp_path,
) -> None:
    snapshot, _, record, _ = (
        build_snapshot(
            tmp_path
        )
    )

    assert (
        "site:operational"
        in snapshot.affected_sites
    )

    for site in record.report_payload.get(
        "affected_sites",
        (),
    ):
        assert site in snapshot.affected_sites


def test_metadata_is_merged(
    tmp_path,
) -> None:
    snapshot, *_ = build_snapshot(
        tmp_path
    )

    assert (
        snapshot.metadata["environment"]
        == "test"
    )

    assert (
        snapshot.metadata["display"]
        == "main-wall"
    )

    assert (
        snapshot.metadata["builder_service"]
        == BUILDER_SERVICE_NAME
    )


def test_snapshot_fingerprint_is_valid(
    tmp_path,
) -> None:
    snapshot, *_ = build_snapshot(
        tmp_path
    )

    assert (
        snapshot.dashboard_fingerprint
        == snapshot.calculate_fingerprint()
    )


def test_builder_is_deterministic(
    tmp_path,
) -> None:
    snapshot, store, _, state = (
        build_snapshot(
            tmp_path
        )
    )

    second = (
        build_noc_wall_dashboard_snapshot(
            report_store=store,
            operational_state=state,
            generated_at=GENERATED_AT,
            metadata={
                "display":
                    "main-wall",
            },
        )
    )

    assert (
        snapshot.dashboard_id
        == second.dashboard_id
    )

    assert (
        snapshot.dashboard_fingerprint
        == second.dashboard_fingerprint
    )


def test_tampered_report_store_rejected(
    tmp_path,
) -> None:
    store, record = make_report_store(
        tmp_path
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET report_title = ?
            WHERE sequence_number = ?
            """,
            (
                "Tampered report",
                record.sequence_number,
            ),
        )
        connection.commit()

    with pytest.raises(
        ValueError,
        match="audit",
    ):
        build_noc_wall_dashboard_snapshot(
            report_store=store,
            operational_state=(
                make_operational_state()
            ),
            generated_at=GENERATED_AT,
        )


def test_generated_at_before_latest_report_rejected(
    tmp_path,
) -> None:
    store, _ = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="generated_at",
    ):
        build_noc_wall_dashboard_snapshot(
            report_store=store,
            operational_state=(
                make_operational_state()
            ),
            generated_at=(
                STORED_AT
                - timedelta(
                    seconds=1
                )
            ),
        )


def test_naive_generated_at_rejected(
    tmp_path,
) -> None:
    store, _ = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_noc_wall_dashboard_snapshot(
            report_store=store,
            operational_state=(
                make_operational_state()
            ),
            generated_at=(
                GENERATED_AT.replace(
                    tzinfo=None
                )
            ),
        )


def test_invalid_report_store_rejected(
    tmp_path,
) -> None:
    with pytest.raises(
        TypeError,
        match="report_store",
    ):
        build_noc_wall_dashboard_snapshot(
            report_store="invalid",
            operational_state=(
                make_operational_state()
            ),
            generated_at=GENERATED_AT,
        )


def test_invalid_operational_state_rejected(
    tmp_path,
) -> None:
    store, _ = make_report_store(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="operational_state",
    ):
        build_noc_wall_dashboard_snapshot(
            report_store=store,
            operational_state="invalid",
            generated_at=GENERATED_AT,
        )


def test_invalid_metadata_rejected(
    tmp_path,
) -> None:
    store, _ = make_report_store(
        tmp_path
    )

    with pytest.raises(
        TypeError,
        match="metadata",
    ):
        build_noc_wall_dashboard_snapshot(
            report_store=store,
            operational_state=(
                make_operational_state()
            ),
            generated_at=GENERATED_AT,
            metadata="invalid",
        )


def test_operational_state_counter_validation() -> None:
    with pytest.raises(
        ValueError,
        match="site counters",
    ):
        make_operational_state(
            total_sites=10
        )


def test_snapshot_never_grants_execution(
    tmp_path,
) -> None:
    snapshot, *_ = build_snapshot(
        tmp_path
    )

    assert snapshot.incident_created is False
    assert snapshot.recommendation_executed is False
    assert snapshot.decision_created is False
    assert snapshot.authorization_created is False
    assert snapshot.execution_allowed is False
    assert snapshot.can_execute is False

    payload = snapshot.to_dict()

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["display_only"]
        is True
    )
