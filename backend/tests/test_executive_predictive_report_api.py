from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from app.services.executive_predictive_report_api import (
    API_SERVICE_NAME,
    ExecutivePredictiveReportAPI,
    ExecutivePredictiveReportAPIIntegrityError,
    ExecutivePredictiveReportAPINotFound,
    ExecutivePredictiveReportAPIResponse,
    export_executive_predictive_report,
    get_executive_predictive_report,
    list_executive_predictive_reports,
)
from tests.test_executive_predictive_report_store import (
    STORED_AT,
    append_report,
)


AUDITED_AT = (
    STORED_AT
    + timedelta(
        minutes=10
    )
)

EXPORTED_AT = (
    STORED_AT
    + timedelta(
        minutes=5
    )
)


def test_list_reports(
    tmp_path,
) -> None:
    record, store, *_ = append_report(
        tmp_path
    )

    response = (
        list_executive_predictive_reports(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    assert isinstance(
        response,
        ExecutivePredictiveReportAPIResponse,
    )

    assert response.success is True
    assert response.operation == "list_reports"
    assert response.data["returned_count"] == 1

    assert (
        response.data["reports"][0]["report_id"]
        == record.report_id
    )


def test_get_report(
    tmp_path,
) -> None:
    record, store, *_ = append_report(
        tmp_path
    )

    response = (
        get_executive_predictive_report(
            store=store,
            report_id=record.report_id,
            audited_at=AUDITED_AT,
        )
    )

    assert response.success is True
    assert response.operation == "get_report"

    assert (
        response.data["report"]["report_id"]
        == record.report_id
    )


def test_export_report_pdf(
    tmp_path,
) -> None:
    record, store, *_ = append_report(
        tmp_path
    )

    output = (
        tmp_path
        / "exports"
        / "report.pdf"
    )

    response = (
        export_executive_predictive_report(
            store=store,
            report_id=record.report_id,
            output_path=output,
            exported_at=EXPORTED_AT,
            audited_at=AUDITED_AT,
        )
    )

    assert response.success is True
    assert response.operation == "export_pdf"
    assert output.exists()

    assert (
        response.data["pdf"]["report_id"]
        == record.report_id
    )


def test_missing_report_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    api = ExecutivePredictiveReportAPI(
        store=store
    )

    with pytest.raises(
        ExecutivePredictiveReportAPINotFound,
    ):
        api.get_report(
            report_id=(
                "executive-predictive-report:"
                "missing"
            ),
            audited_at=AUDITED_AT,
        )


def test_tampered_store_rejected(
    tmp_path,
) -> None:
    record, store, *_ = append_report(
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
                "Tampered",
                record.sequence_number,
            ),
        )
        connection.commit()

    api = ExecutivePredictiveReportAPI(
        store=store
    )

    with pytest.raises(
        ExecutivePredictiveReportAPIIntegrityError,
    ):
        api.list_reports(
            audited_at=AUDITED_AT,
        )


def test_api_response_never_grants_execution(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    response = (
        list_executive_predictive_reports(
            store=store,
            audited_at=AUDITED_AT,
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


def test_api_identity(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    response = (
        list_executive_predictive_reports(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    assert response.service_name == (
        API_SERVICE_NAME
    )

    assert response.service_version == "1.0.0"


def test_invalid_store_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="store",
    ):
        ExecutivePredictiveReportAPI(
            store="invalid"
        )


def test_empty_report_id_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    api = ExecutivePredictiveReportAPI(
        store=store
    )

    with pytest.raises(
        ValueError,
        match="report_id",
    ):
        api.get_report(
            report_id=" ",
            audited_at=AUDITED_AT,
        )


def test_audit_store_operation(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    api = ExecutivePredictiveReportAPI(
        store=store
    )

    response = api.audit_store(
        audited_at=AUDITED_AT
    )

    assert response.success is True
    assert response.operation == "audit_store"

    assert (
        response.data["audit"]["audit_valid"]
        is True
    )
