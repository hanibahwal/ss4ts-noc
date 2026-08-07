from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import hashlib
import sqlite3

import pytest

from app.services.executive_predictive_report_pdf import (
    PDF_SERVICE_NAME,
    ExecutivePredictiveReportPDFError,
    ExecutivePredictiveReportPDFExistsError,
    ExecutivePredictiveReportPDFExport,
    ExecutivePredictiveReportPDFIntegrityError,
    ExecutivePredictiveReportPDFRenderer,
    export_executive_predictive_report_pdf,
)
from app.services.executive_predictive_report_store import (
    ExecutivePredictiveReportStore,
)
from tests.test_executive_predictive_report_builder import (
    GENERATED_AT,
)
from tests.test_executive_predictive_report_store import (
    STORED_AT,
    append_report,
)


EXPORTED_AT = (
    STORED_AT
    + timedelta(
        minutes=5
    )
)


def make_stored_report(
    tmp_path,
):
    (
        record,
        store,
        report,
        validation,
        predictive_store,
        audit,
    ) = append_report(
        tmp_path
    )

    return (
        record,
        store,
        report,
        validation,
        predictive_store,
        audit,
    )


def test_render_pdf_bytes(
    tmp_path,
) -> None:
    record, *_ = make_stored_report(
        tmp_path
    )

    renderer = (
        ExecutivePredictiveReportPDFRenderer()
    )

    pdf_bytes, page_count, exported_at = (
        renderer.render_bytes(
            record=record,
            exported_at=EXPORTED_AT,
        )
    )

    assert pdf_bytes.startswith(
        b"%PDF-1.4"
    )

    assert pdf_bytes.rstrip().endswith(
        b"%%EOF"
    )

    assert page_count >= 1
    assert exported_at == EXPORTED_AT


def test_export_pdf_file(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    output = (
        tmp_path
        / "exports"
        / "executive-report.pdf"
    )

    result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=output,
            exported_at=EXPORTED_AT,
        )
    )

    assert isinstance(
        result,
        ExecutivePredictiveReportPDFExport,
    )

    assert output.exists()
    assert output.is_file()

    content = output.read_bytes()

    assert content.startswith(
        b"%PDF-1.4"
    )

    assert result.report_id == record.report_id
    assert result.file_name == output.name

    assert result.content_type == (
        "application/pdf"
    )

    assert result.file_size_bytes == len(
        content
    )

    assert result.pdf_sha256 == (
        hashlib.sha256(
            content
        ).hexdigest()
    )

    assert result.page_count >= 1
    assert result.pdf_rendered is True


def test_export_to_directory(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    output_directory = (
        tmp_path
        / "exports"
    )

    output_directory.mkdir()

    result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=output_directory,
            exported_at=EXPORTED_AT,
        )
    )

    assert result.file_name.endswith(
        ".pdf"
    )

    assert (
        output_directory
        / result.file_name
    ).exists()


def test_export_to_new_directory_path(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    output_directory = (
        tmp_path
        / "new-export-directory"
    )

    result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=output_directory,
            exported_at=EXPORTED_AT,
        )
    )

    assert result.file_name.endswith(
        ".pdf"
    )

    assert (
        output_directory
        / result.file_name
    ).exists()


def test_pdf_contains_report_identity(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    output = (
        tmp_path
        / "report.pdf"
    )

    export_executive_predictive_report_pdf(
        store=store,
        report_id=record.report_id,
        output_path=output,
        exported_at=EXPORTED_AT,
    )

    content = output.read_bytes()

    assert record.report_id.encode(
        "latin-1"
    ) in content

    assert record.report_fingerprint.encode(
        "latin-1"
    ) in content

    assert record.record_hash.encode(
        "latin-1"
    ) in content


def test_export_is_deterministic(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    first = (
        tmp_path
        / "first.pdf"
    )

    second = (
        tmp_path
        / "second.pdf"
    )

    first_result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=first,
            exported_at=EXPORTED_AT,
        )
    )

    second_result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=second,
            exported_at=EXPORTED_AT,
        )
    )

    assert (
        first.read_bytes()
        == second.read_bytes()
    )

    assert (
        first_result.pdf_sha256
        == second_result.pdf_sha256
    )


def test_existing_file_rejected(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    output = (
        tmp_path
        / "report.pdf"
    )

    output.write_bytes(
        b"existing"
    )

    with pytest.raises(
        ExecutivePredictiveReportPDFExistsError,
    ):
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=output,
            exported_at=EXPORTED_AT,
        )

    assert output.read_bytes() == b"existing"


def test_existing_file_can_be_overwritten(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    output = (
        tmp_path
        / "report.pdf"
    )

    output.write_bytes(
        b"existing"
    )

    result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=output,
            exported_at=EXPORTED_AT,
            overwrite=True,
        )
    )

    assert output.read_bytes().startswith(
        b"%PDF-1.4"
    )

    assert result.file_size_bytes > 0


def test_missing_report_rejected(
    tmp_path,
) -> None:
    store = ExecutivePredictiveReportStore(
        tmp_path
        / "reports.db"
    )

    with pytest.raises(
        ExecutivePredictiveReportPDFError,
        match="not found",
    ):
        export_executive_predictive_report_pdf(
            store=store,
            report_id=(
                "executive-predictive-report:"
                "missing"
            ),
            output_path=(
                tmp_path
                / "missing.pdf"
            ),
            exported_at=EXPORTED_AT,
        )


def test_tampered_store_chain_rejected(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
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
        ExecutivePredictiveReportPDFIntegrityError,
        match="chain",
    ):
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=(
                tmp_path
                / "tampered.pdf"
            ),
            exported_at=EXPORTED_AT,
        )


def test_invalid_record_hash_rejected(
    tmp_path,
) -> None:
    record, *_ = make_stored_report(
        tmp_path
    )

    invalid_record = replace(
        record,
        record_hash=(
            "f" * 64
        ),
    )

    renderer = (
        ExecutivePredictiveReportPDFRenderer()
    )

    with pytest.raises(
        ExecutivePredictiveReportPDFIntegrityError,
        match="hash",
    ):
        renderer.render_bytes(
            record=invalid_record,
            exported_at=EXPORTED_AT,
        )


def test_invalid_validation_rejected(
    tmp_path,
) -> None:
    record, *_ = make_stored_report(
        tmp_path
    )

    invalid_record = replace(
        record,
        validation_valid=False,
    )

    invalid_record = replace(
        invalid_record,
        record_hash=(
            invalid_record.calculate_hash()
        ),
    )

    renderer = (
        ExecutivePredictiveReportPDFRenderer()
    )

    with pytest.raises(
        ExecutivePredictiveReportPDFIntegrityError,
        match="validation",
    ):
        renderer.render_bytes(
            record=invalid_record,
            exported_at=EXPORTED_AT,
        )


def test_invalid_source_audit_rejected(
    tmp_path,
) -> None:
    record, *_ = make_stored_report(
        tmp_path
    )

    invalid_record = replace(
        record,
        source_audit_valid=False,
    )

    invalid_record = replace(
        invalid_record,
        record_hash=(
            invalid_record.calculate_hash()
        ),
    )

    renderer = (
        ExecutivePredictiveReportPDFRenderer()
    )

    with pytest.raises(
        ExecutivePredictiveReportPDFIntegrityError,
        match="audit",
    ):
        renderer.render_bytes(
            record=invalid_record,
            exported_at=EXPORTED_AT,
        )


def test_export_before_stored_at_rejected(
    tmp_path,
) -> None:
    record, *_ = make_stored_report(
        tmp_path
    )

    renderer = (
        ExecutivePredictiveReportPDFRenderer()
    )

    with pytest.raises(
        ExecutivePredictiveReportPDFIntegrityError,
        match="exported_at",
    ):
        renderer.render_bytes(
            record=record,
            exported_at=(
                STORED_AT
                - timedelta(
                    seconds=1
                )
            ),
        )


def test_naive_exported_at_rejected(
    tmp_path,
) -> None:
    record, *_ = make_stored_report(
        tmp_path
    )

    renderer = (
        ExecutivePredictiveReportPDFRenderer()
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        renderer.render_bytes(
            record=record,
            exported_at=(
                GENERATED_AT.replace(
                    tzinfo=None
                )
            ),
        )


def test_export_manifest_never_grants_execution(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=(
                tmp_path
                / "report.pdf"
            ),
            exported_at=EXPORTED_AT,
        )
    )

    payload = result.to_dict()

    assert result.pdf_rendered is True
    assert result.report_created is False
    assert result.incident_created is False
    assert result.recommendation_executed is False
    assert result.decision_created is False
    assert result.authorization_created is False
    assert result.execution_allowed is False
    assert result.can_execute is False

    assert payload["pdf_rendered"] is True
    assert payload["can_execute"] is False

    assert (
        payload["safety"][
            "render_only"
        ]
        is True
    )


def test_renderer_identity(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    result = (
        export_executive_predictive_report_pdf(
            store=store,
            report_id=record.report_id,
            output_path=(
                tmp_path
                / "report.pdf"
            ),
            exported_at=EXPORTED_AT,
        )
    )

    assert result.renderer_name == (
        PDF_SERVICE_NAME
    )

    assert result.renderer_version == "1.0.0"


def test_invalid_argument_types_rejected(
    tmp_path,
) -> None:
    record, store, *_ = make_stored_report(
        tmp_path
    )

    renderer = (
        ExecutivePredictiveReportPDFRenderer()
    )

    with pytest.raises(
        TypeError,
        match="record",
    ):
        renderer.render_bytes(
            record="invalid",
            exported_at=EXPORTED_AT,
        )

    with pytest.raises(
        TypeError,
        match="store",
    ):
        renderer.export(
            store="invalid",
            report_id=record.report_id,
            output_path=(
                tmp_path
                / "report.pdf"
            ),
            exported_at=EXPORTED_AT,
        )

    with pytest.raises(
        TypeError,
        match="overwrite",
    ):
        renderer.export(
            store=store,
            report_id=record.report_id,
            output_path=(
                tmp_path
                / "report.pdf"
            ),
            exported_at=EXPORTED_AT,
            overwrite="yes",
        )


def test_empty_report_id_rejected(
    tmp_path,
) -> None:
    _, store, *_ = make_stored_report(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="report_id",
    ):
        export_executive_predictive_report_pdf(
            store=store,
            report_id=" ",
            output_path=(
                tmp_path
                / "report.pdf"
            ),
            exported_at=EXPORTED_AT,
        )
