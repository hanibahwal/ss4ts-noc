from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from app.services.noc_wall_dashboard_api import (
    API_SERVICE_NAME,
    NOCWallDashboardAPI,
    NOCWallDashboardAPIIntegrityError,
    NOCWallDashboardAPINotFound,
    NOCWallDashboardAPIResponse,
    get_latest_noc_wall_dashboard,
    get_noc_wall_dashboard_health,
    get_noc_wall_dashboard_snapshot,
    list_noc_wall_dashboard_history,
)
from app.services.noc_wall_dashboard_store import (
    NOCWallDashboardStore,
)
from tests.test_noc_wall_dashboard_store import (
    STORED_AT,
    append_snapshot,
)


GENERATED_AT = (
    STORED_AT
    + timedelta(
        minutes=5
    )
)


def test_latest_dashboard(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    response = (
        get_latest_noc_wall_dashboard(
            store=store,
            generated_at=GENERATED_AT,
        )
    )

    assert isinstance(
        response,
        NOCWallDashboardAPIResponse,
    )

    assert response.success is True
    assert response.operation == "latest"

    assert (
        response.data[
            "dashboard"
        ]["dashboard_id"]
        == record.dashboard_id
    )


def test_history(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    response = (
        list_noc_wall_dashboard_history(
            store=store,
            generated_at=GENERATED_AT,
        )
    )

    assert response.success is True
    assert response.operation == "history"
    assert response.data["returned_count"] == 1

    assert (
        response.data[
            "dashboards"
        ][0]["dashboard_id"]
        == record.dashboard_id
    )


def test_history_status_filter(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    response = (
        list_noc_wall_dashboard_history(
            store=store,
            status=record.overall_status,
            generated_at=GENERATED_AT,
        )
    )

    assert response.data["returned_count"] == 1

    empty = (
        list_noc_wall_dashboard_history(
            store=store,
            status="healthy",
            generated_at=GENERATED_AT,
        )
    )

    if record.overall_status != "healthy":
        assert empty.data["returned_count"] == 0


def test_get_snapshot(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    response = (
        get_noc_wall_dashboard_snapshot(
            store=store,
            dashboard_id=record.dashboard_id,
            generated_at=GENERATED_AT,
        )
    )

    assert response.success is True
    assert response.operation == "get_snapshot"

    assert (
        response.data[
            "dashboard"
        ]["record_hash"]
        == record.record_hash
    )


def test_get_by_fingerprint(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    api = NOCWallDashboardAPI(
        store=store
    )

    response = api.get_by_fingerprint(
        dashboard_fingerprint=(
            record.dashboard_fingerprint
        ),
        generated_at=GENERATED_AT,
    )

    assert response.success is True

    assert (
        response.data[
            "dashboard"
        ]["dashboard_id"]
        == record.dashboard_id
    )


def test_health(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    response = (
        get_noc_wall_dashboard_health(
            store=store,
            generated_at=GENERATED_AT,
        )
    )

    assert response.success is True
    assert response.operation == "health"

    assert (
        response.data[
            "store_chain_valid"
        ]
        is True
    )

    assert (
        response.data[
            "latest_dashboard_id"
        ]
        == record.dashboard_id
    )


def test_empty_store_health(
    tmp_path,
) -> None:
    store = NOCWallDashboardStore(
        tmp_path
        / "dashboard.db"
    )

    response = (
        get_noc_wall_dashboard_health(
            store=store,
            generated_at=GENERATED_AT,
        )
    )

    assert response.success is True
    assert response.data["store_record_count"] == 0

    assert (
        response.data["latest_dashboard_id"]
        is None
    )


def test_latest_empty_store_rejected(
    tmp_path,
) -> None:
    store = NOCWallDashboardStore(
        tmp_path
        / "dashboard.db"
    )

    with pytest.raises(
        NOCWallDashboardAPINotFound,
    ):
        get_latest_noc_wall_dashboard(
            store=store,
            generated_at=GENERATED_AT,
        )


def test_missing_snapshot_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    with pytest.raises(
        NOCWallDashboardAPINotFound,
    ):
        get_noc_wall_dashboard_snapshot(
            store=store,
            dashboard_id=(
                "noc-wall-dashboard:missing"
            ),
            generated_at=GENERATED_AT,
        )


def test_tampered_store_rejected(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET overall_health_score = ?
            WHERE sequence_number = ?
            """,
            (
                1.0,
                record.sequence_number,
            ),
        )

        connection.commit()

    api = NOCWallDashboardAPI(
        store=store
    )

    with pytest.raises(
        NOCWallDashboardAPIIntegrityError,
    ):
        api.latest(
            generated_at=GENERATED_AT
        )


def test_health_reports_tampering(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET overall_status = ?
            WHERE sequence_number = ?
            """,
            (
                "healthy",
                record.sequence_number,
            ),
        )

        connection.commit()

    response = (
        get_noc_wall_dashboard_health(
            store=store,
            generated_at=GENERATED_AT,
        )
    )

    assert response.success is False

    assert (
        response.data["store_chain_valid"]
        is False
    )

    assert (
        response.data["service_status"]
        == "integrity_failure"
    )


def test_invalid_status_filter_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="status",
    ):
        list_noc_wall_dashboard_history(
            store=store,
            status="invalid",
            generated_at=GENERATED_AT,
        )


def test_invalid_limit_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        list_noc_wall_dashboard_history(
            store=store,
            limit=0,
            generated_at=GENERATED_AT,
        )


def test_invalid_store_type_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="store",
    ):
        NOCWallDashboardAPI(
            store="invalid"
        )


def test_naive_generated_at_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        get_noc_wall_dashboard_health(
            store=store,
            generated_at=(
                GENERATED_AT.replace(
                    tzinfo=None
                )
            ),
        )


def test_api_identity(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    response = (
        get_noc_wall_dashboard_health(
            store=store,
            generated_at=GENERATED_AT,
        )
    )

    assert response.service_name == (
        API_SERVICE_NAME
    )

    assert response.service_version == "1.0.0"


def test_api_never_grants_execution(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    response = (
        get_noc_wall_dashboard_health(
            store=store,
            generated_at=GENERATED_AT,
        )
    )

    payload = response.to_dict()

    assert response.incident_created is False
    assert response.recommendation_executed is False
    assert response.decision_created is False
    assert response.authorization_created is False
    assert response.execution_allowed is False
    assert response.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["read_only_api"]
        is True
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )
