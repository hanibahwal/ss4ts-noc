from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from app.services.executive_predictive_report_store import (
    GENESIS_RECORD_HASH,
    ExecutivePredictiveReportDuplicate,
    ExecutivePredictiveReportIntegrityError,
    ExecutivePredictiveReportRecord,
    ExecutivePredictiveReportStore,
)
from app.services.executive_predictive_report_validation import (
    validate_executive_predictive_report,
)
from tests.test_executive_predictive_report_builder import (
    GENERATED_AT,
    build_report,
)


VALIDATED_AT = (
    GENERATED_AT
    + timedelta(
        minutes=5
    )
)

STORED_AT = (
    GENERATED_AT
    + timedelta(
        minutes=10
    )
)


def make_validated_report(
    tmp_path,
    *,
    count: int = 2,
):
    report, predictive_store, audit = (
        build_report(
            tmp_path,
            count=count,
        )
    )

    validation = (
        validate_executive_predictive_report(
            report=report,
            store=predictive_store,
            source_audit=audit,
            validated_at=VALIDATED_AT,
        )
    )

    assert validation.validation_valid is True
    assert validation.report_accepted is True

    return (
        report,
        validation,
        predictive_store,
        audit,
    )


def make_report_store(
    tmp_path,
):
    return ExecutivePredictiveReportStore(
        tmp_path
        / "executive-predictive-reports.db"
    )


def append_report(
    tmp_path,
    *,
    report_store=None,
    count: int = 2,
):
    (
        report,
        validation,
        predictive_store,
        audit,
    ) = make_validated_report(
        tmp_path,
        count=count,
    )

    store = (
        report_store
        or make_report_store(
            tmp_path
        )
    )

    record = store.append(
        report=report,
        validation=validation,
        stored_at=STORED_AT,
    )

    return (
        record,
        store,
        report,
        validation,
        predictive_store,
        audit,
    )


def test_append_validated_report(
    tmp_path,
) -> None:
    (
        record,
        store,
        report,
        validation,
        _,
        _,
    ) = append_report(
        tmp_path
    )

    assert isinstance(
        record,
        ExecutivePredictiveReportRecord,
    )

    assert record.sequence_number == 1
    assert record.report_id == report.report_id

    assert (
        record.report_fingerprint
        == report.report_fingerprint
    )

    assert record.validation_valid is True
    assert record.previous_record_hash == (
        GENESIS_RECORD_HASH
    )

    assert record.verify_hash() is True
    assert store.count() == 1

    assert (
        record.validation_payload[
            "report_id"
        ]
        == validation.report_id
    )


def test_record_never_grants_execution(
    tmp_path,
) -> None:
    record, *_ = append_report(
        tmp_path
    )

    payload = record.to_dict()

    assert record.report_created is False
    assert record.pdf_rendered is False
    assert record.incident_created is False
    assert record.recommendation_executed is False
    assert record.decision_created is False
    assert record.authorization_created is False
    assert record.execution_allowed is False
    assert record.can_execute is False

    assert payload["can_execute"] is False
    assert (
        payload["safety"][
            "immutable_record"
        ]
        is True
    )


def test_get_report_by_id(
    tmp_path,
) -> None:
    record, store, *_ = append_report(
        tmp_path
    )

    loaded = store.get(
        record.report_id
    )

    assert loaded == record


def test_get_report_by_fingerprint(
    tmp_path,
) -> None:
    record, store, *_ = append_report(
        tmp_path
    )

    loaded = store.get_by_fingerprint(
        record.report_fingerprint
    )

    assert loaded == record


def test_missing_report_returns_none(
    tmp_path,
) -> None:
    store = make_report_store(
        tmp_path
    )

    assert (
        store.get(
            "executive-predictive-report:missing"
        )
        is None
    )

    assert (
        store.get_by_fingerprint(
            "f" * 64
        )
        is None
    )


def test_duplicate_report_rejected(
    tmp_path,
) -> None:
    (
        record,
        store,
        report,
        validation,
        _,
        _,
    ) = append_report(
        tmp_path
    )

    assert record.sequence_number == 1

    with pytest.raises(
        ExecutivePredictiveReportDuplicate,
    ):
        store.append(
            report=report,
            validation=validation,
            stored_at=(
                STORED_AT
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_invalid_validation_rejected(
    tmp_path,
) -> None:
    (
        report,
        validation,
        _,
        _,
    ) = make_validated_report(
        tmp_path
    )

    invalid_validation = replace(
        validation,
        validation_valid=False,
        report_accepted=False,
        validation_errors=(
            "manual failure",
        ),
    )

    store = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ExecutivePredictiveReportIntegrityError,
        match="validated",
    ):
        store.append(
            report=report,
            validation=invalid_validation,
            stored_at=STORED_AT,
        )


def test_validation_report_id_mismatch_rejected(
    tmp_path,
) -> None:
    (
        report,
        validation,
        _,
        _,
    ) = make_validated_report(
        tmp_path
    )

    invalid_validation = replace(
        validation,
        report_id=(
            "executive-predictive-report:"
            "different"
        ),
    )

    store = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ExecutivePredictiveReportIntegrityError,
        match="report_id",
    ):
        store.append(
            report=report,
            validation=invalid_validation,
            stored_at=STORED_AT,
        )


def test_validation_fingerprint_mismatch_rejected(
    tmp_path,
) -> None:
    (
        report,
        validation,
        _,
        _,
    ) = make_validated_report(
        tmp_path
    )

    invalid_validation = replace(
        validation,
        report_fingerprint=(
            "f" * 64
        ),
    )

    store = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ExecutivePredictiveReportIntegrityError,
        match="fingerprint",
    ):
        store.append(
            report=report,
            validation=invalid_validation,
            stored_at=STORED_AT,
        )


def test_tampered_report_rejected(
    tmp_path,
) -> None:
    (
        report,
        validation,
        _,
        _,
    ) = make_validated_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "executive_summary",
        "Tampered report",
    )

    store = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ExecutivePredictiveReportIntegrityError,
        match="fingerprint",
    ):
        store.append(
            report=report,
            validation=validation,
            stored_at=STORED_AT,
        )


def test_stored_at_before_validation_rejected(
    tmp_path,
) -> None:
    (
        report,
        validation,
        _,
        _,
    ) = make_validated_report(
        tmp_path
    )

    store = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ExecutivePredictiveReportIntegrityError,
        match="stored_at",
    ):
        store.append(
            report=report,
            validation=validation,
            stored_at=(
                validation.validated_at
                - timedelta(
                    seconds=1
                )
            ),
        )


def test_list_records_is_sequence_ordered(
    tmp_path,
) -> None:
    first_path = (
        tmp_path
        / "first-source"
    )

    second_path = (
        tmp_path
        / "second-source"
    )

    first_path.mkdir()
    second_path.mkdir()

    report_store = make_report_store(
        tmp_path
    )

    (
        first_report,
        first_validation,
        _,
        _,
    ) = make_validated_report(
        first_path
    )

    first = report_store.append(
        report=first_report,
        validation=first_validation,
        stored_at=STORED_AT,
    )

    (
        second_report,
        second_validation,
        _,
        _,
    ) = make_validated_report(
        second_path,
        count=1,
    )

    object.__setattr__(
        second_report,
        "report_id",
        (
            "executive-predictive-report:"
            "second"
        ),
    )

    object.__setattr__(
        second_report,
        "report_fingerprint",
        (
            second_report
            .calculate_fingerprint()
        ),
    )

    second_validation = replace(
        second_validation,
        report_id=second_report.report_id,
        report_fingerprint=(
            second_report.report_fingerprint
        ),
    )

    second = report_store.append(
        report=second_report,
        validation=second_validation,
        stored_at=(
            STORED_AT
            + timedelta(
                minutes=1
            )
        ),
    )

    records = (
        report_store.list_records()
    )

    assert tuple(
        record.sequence_number
        for record in records
    ) == (
        1,
        2,
    )

    assert (
        second.previous_record_hash
        == first.record_hash
    )


def test_verify_chain_valid(
    tmp_path,
) -> None:
    _, store, *_ = append_report(
        tmp_path
    )

    assert store.verify_chain() is True


def test_verify_chain_detects_tampering(
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
                "Tampered Title",
                record.sequence_number,
            ),
        )
        connection.commit()

    assert store.verify_chain() is False


def test_invalid_input_types_rejected(
    tmp_path,
) -> None:
    store = make_report_store(
        tmp_path
    )

    source_path = (
        tmp_path
        / "source"
    )

    source_path.mkdir()

    (
        report,
        validation,
        _,
        _,
    ) = make_validated_report(
        source_path
    )

    with pytest.raises(
        TypeError,
        match="report",
    ):
        store.append(
            report="invalid",
            validation=validation,
            stored_at=STORED_AT,
        )

    with pytest.raises(
        TypeError,
        match="validation",
    ):
        store.append(
            report=report,
            validation="invalid",
            stored_at=STORED_AT,
        )


def test_invalid_lookup_values_rejected(
    tmp_path,
) -> None:
    store = make_report_store(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="report_id",
    ):
        store.get(" ")

    with pytest.raises(
        ValueError,
        match="report_fingerprint",
    ):
        store.get_by_fingerprint(" ")

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        store.list_records(
            limit=0
        )
