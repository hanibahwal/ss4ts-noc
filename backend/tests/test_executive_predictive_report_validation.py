from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from app.models.executive_predictive_report import (
    ExecutivePredictiveOutlook,
    ExecutivePredictiveRiskClass,
)
from app.services.executive_predictive_report_validation import (
    ExecutivePredictiveReportValidationResult,
    ExecutivePredictiveReportValidator,
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


def validate_report(
    report,
    store,
    audit,
):
    return validate_executive_predictive_report(
        report=report,
        store=store,
        source_audit=audit,
        validated_at=VALIDATED_AT,
    )


def test_valid_report_is_accepted(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert isinstance(
        result,
        ExecutivePredictiveReportValidationResult,
    )

    assert result.validation_valid is True
    assert result.report_accepted is True
    assert result.validation_errors == ()

    assert all(
        result.checks.values()
    )


def test_validation_result_identity(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert result.report_id == report.report_id
    assert (
        result.report_fingerprint
        == report.report_fingerprint
    )


def test_validation_is_read_only(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    before_count = store.count()
    before_fingerprint = (
        report.report_fingerprint
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert result.validation_valid is True
    assert store.count() == before_count
    assert (
        report.report_fingerprint
        == before_fingerprint
    )


def test_result_never_grants_execution(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    payload = result.to_dict()

    assert result.report_created is False
    assert result.pdf_rendered is False
    assert result.incident_created is False
    assert result.recommendation_executed is False
    assert result.decision_created is False
    assert result.authorization_created is False
    assert result.execution_allowed is False
    assert result.can_execute is False

    assert payload["can_execute"] is False
    assert (
        payload["safety"][
            "report_validation_only"
        ]
        is True
    )


def test_fingerprint_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "executive_summary",
        "Tampered executive summary",
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "fingerprint_valid"
        ]
        is False
    )

    assert result.validation_valid is False
    assert result.report_accepted is False


def test_source_audit_binding_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "source_audit_id",
        "predictive-store-audit:tampered",
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "source_audit_valid"
        ]
        is False
    )

    assert result.validation_valid is False


def test_invalid_source_audit_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        audit,
        "record_hashes_valid",
        False,
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "source_audit_valid"
        ]
        is False
    )


def test_prediction_binding_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "source_prediction_ids",
        (
            "prediction:tampered",
            *report.source_prediction_ids[1:],
        ),
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "source_prediction_bindings_valid"
        ]
        is False
    )


def test_record_hash_binding_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "source_record_hashes",
        (
            "f" * 64,
            *report.source_record_hashes[1:],
        ),
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "source_record_hashes_valid"
        ]
        is False
    )


def test_prediction_count_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "prediction_count",
        99,
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "source_record_count_valid"
        ]
        is False
    )

    assert (
        result.checks[
            "prediction_counts_valid"
        ]
        is False
    )


def test_risk_class_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "overall_risk_class",
        ExecutivePredictiveRiskClass.LOW,
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "risk_class_valid"
        ]
        is False
    )


def test_outlook_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "service_outlook",
        ExecutivePredictiveOutlook.STABLE,
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "service_outlook_valid"
        ]
        is False
    )


def test_health_score_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "overall_health_score",
        100.0,
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "health_score_valid"
        ]
        is False
    )


def test_report_period_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "report_period_start",
        (
            report.report_period_start
            - timedelta(
                days=1
            )
        ),
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "report_period_valid"
        ]
        is False
    )


def test_validation_before_report_generation_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    result = (
        validate_executive_predictive_report(
            report=report,
            store=store,
            source_audit=audit,
            validated_at=(
                GENERATED_AT
                - timedelta(
                    seconds=1
                )
            ),
        )
    )

    assert (
        result.checks[
            "generated_at_valid"
        ]
        is False
    )


def test_missing_findings_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "key_findings",
        (),
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "required_content_valid"
        ]
        is False
    )


def test_missing_high_risk_highlights_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "risk_highlights",
        (),
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "required_content_valid"
        ]
        is False
    )


def test_builder_identity_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "generated_by",
        "unknown-builder",
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "builder_identity_valid"
        ]
        is False
    )


def test_schema_version_tampering_detected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "schema_version",
        "99.0",
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        result.checks[
            "schema_version_valid"
        ]
        is False
    )


def test_empty_report_validates(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path,
        count=0,
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert result.validation_valid is True
    assert result.report_accepted is True


def test_validation_errors_name_failed_checks(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    object.__setattr__(
        report,
        "overall_health_score",
        100.0,
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    assert (
        "health_score_valid failed"
        in result.validation_errors
    )


def test_invalid_report_type_rejected(
    tmp_path,
) -> None:
    _, store, audit = build_report(
        tmp_path
    )

    validator = (
        ExecutivePredictiveReportValidator()
    )

    with pytest.raises(
        TypeError,
        match="report",
    ):
        validator.validate(
            report="invalid",
            store=store,
            source_audit=audit,
            validated_at=VALIDATED_AT,
        )


def test_invalid_store_type_rejected(
    tmp_path,
) -> None:
    report, _, audit = build_report(
        tmp_path
    )

    validator = (
        ExecutivePredictiveReportValidator()
    )

    with pytest.raises(
        TypeError,
        match="store",
    ):
        validator.validate(
            report=report,
            store="invalid",
            source_audit=audit,
            validated_at=VALIDATED_AT,
        )


def test_invalid_audit_type_rejected(
    tmp_path,
) -> None:
    report, store, _ = build_report(
        tmp_path
    )

    validator = (
        ExecutivePredictiveReportValidator()
    )

    with pytest.raises(
        TypeError,
        match="source_audit",
    ):
        validator.validate(
            report=report,
            store=store,
            source_audit="invalid",
            validated_at=VALIDATED_AT,
        )


def test_naive_validated_at_rejected(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        validate_executive_predictive_report(
            report=report,
            store=store,
            source_audit=audit,
            validated_at=datetime(
                2026,
                8,
                7,
                3,
                0,
            ),
        )


def test_result_to_dict_contains_all_checks(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    result = validate_report(
        report,
        store,
        audit,
    )

    payload = result.to_dict()

    assert payload["validation_valid"] is True
    assert payload["report_accepted"] is True

    assert set(
        ExecutivePredictiveReportValidator
        .REQUIRED_CHECKS
    ).issubset(
        payload["checks"]
    )
