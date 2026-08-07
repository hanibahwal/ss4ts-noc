from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from app.services.executive_predictive_report_store import (
    ExecutivePredictiveReportStore,
)
from app.services.executive_predictive_report_store_audit import (
    ExecutivePredictiveReportStoreAuditReport,
    ExecutivePredictiveReportStoreAuditor,
    verify_executive_predictive_report_store,
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


def test_valid_store_audit(
    tmp_path,
) -> None:
    record, store, *_ = append_report(
        tmp_path
    )

    audit = (
        verify_executive_predictive_report_store(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    assert isinstance(
        audit,
        ExecutivePredictiveReportStoreAuditReport,
    )

    assert audit.audit_valid is True
    assert audit.record_count == 1
    assert audit.first_sequence_number == 1
    assert audit.last_sequence_number == 1
    assert audit.first_record_hash == record.record_hash
    assert audit.last_record_hash == record.record_hash
    assert audit.audit_errors == ()
    assert all(
        audit.checks.values()
    )


def test_empty_store_is_valid_with_warning(
    tmp_path,
) -> None:
    store = ExecutivePredictiveReportStore(
        tmp_path
        / "reports.db"
    )

    audit = (
        verify_executive_predictive_report_store(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    assert audit.audit_valid is True
    assert audit.record_count == 0
    assert audit.audit_warnings


def test_audit_is_read_only(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    before = store.list_records()

    audit = (
        verify_executive_predictive_report_store(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    after = store.list_records()

    assert audit.audit_valid is True
    assert before == after


def test_audit_never_grants_execution(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    audit = (
        verify_executive_predictive_report_store(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    payload = audit.to_dict()

    assert audit.report_created is False
    assert audit.pdf_rendered is False
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


def test_tampered_record_hash_detected(
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
            SET record_hash = ?
            WHERE sequence_number = ?
            """,
            (
                "f" * 64,
                record.sequence_number,
            ),
        )
        connection.commit()

    audit = (
        verify_executive_predictive_report_store(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    assert audit.audit_valid is False
    assert (
        audit.checks[
            "record_hashes_valid"
        ]
        is False
    )


def test_broken_previous_hash_detected(
    tmp_path,
) -> None:
    first_path = tmp_path / "first"
    second_path = tmp_path / "second"

    first_path.mkdir()
    second_path.mkdir()

    report_store = ExecutivePredictiveReportStore(
        tmp_path
        / "reports.db"
    )

    append_report(
        first_path,
        report_store=report_store,
        count=2,
    )

    second_record, *_ = append_report(
        second_path,
        report_store=report_store,
        count=1,
    )

    with sqlite3.connect(
        report_store.database_path
    ) as connection:
        connection.execute(
            f"""
            UPDATE {report_store.TABLE_NAME}
            SET previous_record_hash = ?
            WHERE sequence_number = ?
            """,
            (
                "f" * 64,
                second_record.sequence_number,
            ),
        )
        connection.commit()

    audit = (
        verify_executive_predictive_report_store(
            store=report_store,
            audited_at=(
                AUDITED_AT
                + timedelta(
                    minutes=2
                )
            ),
        )
    )

    assert audit.audit_valid is False
    assert (
        audit.checks[
            "previous_hash_links_valid"
        ]
        is False
    )


def test_report_payload_binding_detected(
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
            SET report_payload = ?
            WHERE sequence_number = ?
            """,
            (
                '{"report_id":"tampered"}',
                record.sequence_number,
            ),
        )
        connection.commit()

    audit = (
        verify_executive_predictive_report_store(
            store=store,
            audited_at=AUDITED_AT,
        )
    )

    assert audit.audit_valid is False
    assert (
        audit.checks[
            "report_identity_bindings_valid"
        ]
        is False
    )


def test_invalid_store_type_rejected() -> None:
    auditor = (
        ExecutivePredictiveReportStoreAuditor()
    )

    with pytest.raises(
        TypeError,
        match="store",
    ):
        auditor.verify(
            store="invalid",
            audited_at=AUDITED_AT,
        )


def test_naive_audited_at_rejected(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        verify_executive_predictive_report_store(
            store=store,
            audited_at=(
                AUDITED_AT.replace(
                    tzinfo=None
                )
            ),
        )
