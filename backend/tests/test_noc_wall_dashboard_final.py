from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from app.services.noc_wall_dashboard_final import (
    NOCWallDashboardFinalAuditReport,
    NOCWallDashboardHTMLExport,
    NOCWallDashboardHTMLRenderer,
    export_noc_wall_dashboard_html,
    verify_noc_wall_dashboard_store,
)
from app.services.noc_wall_dashboard_store import (
    NOCWallDashboardStore,
)
from tests.test_noc_wall_dashboard_store import (
    STORED_AT,
    append_snapshot,
)


FINAL_AT = (
    STORED_AT
    + timedelta(
        minutes=10
    )
)


def test_final_audit_valid(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    audit = verify_noc_wall_dashboard_store(
        store=store,
        audited_at=FINAL_AT,
    )

    assert isinstance(
        audit,
        NOCWallDashboardFinalAuditReport,
    )

    assert audit.audit_valid is True
    assert audit.record_count == 1

    assert audit.latest_dashboard_id == (
        record.dashboard_id
    )

    assert audit.audit_errors == ()

    assert all(
        audit.checks.values()
    )


def test_empty_store_audit_valid_with_warning(
    tmp_path,
) -> None:
    store = NOCWallDashboardStore(
        tmp_path
        / "dashboard.db"
    )

    audit = verify_noc_wall_dashboard_store(
        store=store,
        audited_at=FINAL_AT,
    )

    assert audit.audit_valid is True
    assert audit.record_count == 0
    assert audit.audit_warnings


def test_tampered_store_fails_final_audit(
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

    audit = verify_noc_wall_dashboard_store(
        store=store,
        audited_at=FINAL_AT,
    )

    assert audit.audit_valid is False

    assert (
        audit.checks[
            "record_hashes_valid"
        ]
        is False
    )


def test_html_export(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    output = (
        tmp_path
        / "wall"
        / "index.html"
    )

    export = export_noc_wall_dashboard_html(
        store=store,
        output_path=output,
        rendered_at=FINAL_AT,
    )

    assert isinstance(
        export,
        NOCWallDashboardHTMLExport,
    )

    assert output.exists()

    assert export.dashboard_id == (
        record.dashboard_id
    )

    assert export.html_size_bytes > 0
    assert len(export.html_sha256) == 64


def test_exported_html_contains_dashboard_data(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    output = (
        tmp_path
        / "index.html"
    )

    export_noc_wall_dashboard_html(
        store=store,
        output_path=output,
        rendered_at=FINAL_AT,
    )

    html = output.read_text(
        encoding="utf-8"
    )

    assert "SS4TS NOC Wall Dashboard" in html
    assert record.dashboard_id in html
    assert record.overall_status in html
    assert str(record.total_sites) in html
    assert str(record.total_devices) in html
    assert str(record.total_links) in html


def test_html_contains_refresh_instruction(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    output = (
        tmp_path
        / "index.html"
    )

    export_noc_wall_dashboard_html(
        store=store,
        output_path=output,
        rendered_at=FINAL_AT,
    )

    html = output.read_text(
        encoding="utf-8"
    )

    assert (
        'http-equiv="refresh"'
        in html
    )

    assert 'content="60"' in html


def test_export_is_deterministic(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    first_path = (
        tmp_path
        / "first.html"
    )

    second_path = (
        tmp_path
        / "second.html"
    )

    first = export_noc_wall_dashboard_html(
        store=store,
        output_path=first_path,
        rendered_at=FINAL_AT,
    )

    second = export_noc_wall_dashboard_html(
        store=store,
        output_path=second_path,
        rendered_at=FINAL_AT,
    )

    assert (
        first.html_sha256
        == second.html_sha256
    )

    assert (
        first_path.read_bytes()
        == second_path.read_bytes()
    )


def test_existing_output_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    output = (
        tmp_path
        / "index.html"
    )

    export_noc_wall_dashboard_html(
        store=store,
        output_path=output,
        rendered_at=FINAL_AT,
    )

    with pytest.raises(
        FileExistsError,
    ):
        export_noc_wall_dashboard_html(
            store=store,
            output_path=output,
            rendered_at=FINAL_AT,
        )


def test_overwrite_allowed(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    output = (
        tmp_path
        / "index.html"
    )

    export_noc_wall_dashboard_html(
        store=store,
        output_path=output,
        rendered_at=FINAL_AT,
    )

    second = export_noc_wall_dashboard_html(
        store=store,
        output_path=output,
        rendered_at=FINAL_AT,
        overwrite=True,
    )

    assert second.html_size_bytes > 0


def test_empty_store_export_rejected(
    tmp_path,
) -> None:
    store = NOCWallDashboardStore(
        tmp_path
        / "dashboard.db"
    )

    with pytest.raises(
        ValueError,
        match="empty",
    ):
        export_noc_wall_dashboard_html(
            store=store,
            output_path=(
                tmp_path
                / "index.html"
            ),
            rendered_at=FINAL_AT,
        )


def test_tampered_store_export_rejected(
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

    with pytest.raises(
        ValueError,
        match="audit",
    ):
        export_noc_wall_dashboard_html(
            store=store,
            output_path=(
                tmp_path
                / "index.html"
            ),
            rendered_at=FINAL_AT,
        )


def test_invalid_store_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="store",
    ):
        verify_noc_wall_dashboard_store(
            store="invalid",
            audited_at=FINAL_AT,
        )


def test_naive_audit_time_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        verify_noc_wall_dashboard_store(
            store=store,
            audited_at=(
                FINAL_AT.replace(
                    tzinfo=None
                )
            ),
        )


def test_final_audit_never_grants_execution(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    audit = verify_noc_wall_dashboard_store(
        store=store,
        audited_at=FINAL_AT,
    )

    payload = audit.to_dict()

    assert audit.incident_created is False
    assert audit.recommendation_executed is False
    assert audit.decision_created is False
    assert audit.authorization_created is False
    assert audit.execution_allowed is False
    assert audit.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["audit_only"]
        is True
    )


def test_html_export_never_grants_execution(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    export = export_noc_wall_dashboard_html(
        store=store,
        output_path=(
            tmp_path
            / "index.html"
        ),
        rendered_at=FINAL_AT,
    )

    payload = export.to_dict()

    assert export.incident_created is False
    assert export.recommendation_executed is False
    assert export.decision_created is False
    assert export.authorization_created is False
    assert export.execution_allowed is False
    assert export.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["display_only"]
        is True
    )


def test_renderer_interface(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    renderer = (
        NOCWallDashboardHTMLRenderer()
    )

    export = renderer.export(
        store=store,
        output_path=(
            tmp_path
            / "index.html"
        ),
        rendered_at=FINAL_AT,
    )

    assert export.html_size_bytes > 0
