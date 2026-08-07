from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.executive_predictive_report import (
    ExecutivePredictiveOutlook,
    ExecutivePredictiveReport,
    ExecutivePredictiveReportType,
    ExecutivePredictiveRiskClass,
)
from app.services.executive_predictive_report_builder import (
    SERVICE_NAME,
    ExecutivePredictiveReportBuilder,
    build_executive_predictive_report,
)
from app.services.predictive_intelligence_store import (
    PredictiveIntelligenceStore,
)
from app.services.predictive_intelligence_store_audit import (
    verify_predictive_intelligence_store,
)
from tests.test_predictive_intelligence import (
    NOW,
)
from tests.test_predictive_intelligence_store import (
    append_prediction,
)


GENERATED_AT = (
    NOW
    + timedelta(
        hours=2
    )
)


def make_source(
    tmp_path,
    *,
    count: int = 2,
):
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive-report-source.db"
    )

    for index in range(
        count
    ):
        suffix = (
            "one"
            if index == 0
            else f"prediction-{index + 1}"
        )

        append_prediction(
            store,
            suffix=suffix,
        )

    audit = (
        verify_predictive_intelligence_store(
            store,
            audited_at=(
                NOW
                + timedelta(
                    minutes=5
                )
            ),
        )
    )

    assert audit.audit_valid is True

    return store, audit


def build_report(
    tmp_path,
    *,
    count: int = 2,
):
    store, audit = make_source(
        tmp_path,
        count=count,
    )

    report = (
        build_executive_predictive_report(
            store=store,
            source_audit=audit,
            report_type=(
                ExecutivePredictiveReportType.WEEKLY
            ),
            report_title=(
                "Weekly Predictive Report"
            ),
            generated_at=GENERATED_AT,
            metadata={
                "region": "Eastern Province",
            },
        )
    )

    return report, store, audit


def test_build_executive_report(
    tmp_path,
) -> None:
    report, store, audit = build_report(
        tmp_path
    )

    assert isinstance(
        report,
        ExecutivePredictiveReport,
    )

    assert report.prediction_count == 2

    assert (
        len(
            report.source_prediction_ids
        )
        == 2
    )

    assert (
        len(
            report.source_record_hashes
        )
        == 2
    )

    assert (
        report.source_audit_id
        == audit.audit_id
    )

    assert report.source_audit_valid is True
    assert store.count() == 2

    assert (
        report.report_fingerprint
        == report.calculate_fingerprint()
    )


def test_report_period_derived_from_records(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert report.report_period_start == NOW

    assert (
        report.report_period_end
        == NOW
        + timedelta(
            hours=1
        )
    )


def test_high_risk_report_summary(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert (
        report.overall_risk_class
        is ExecutivePredictiveRiskClass.HIGH
    )

    assert (
        report.service_outlook
        is ExecutivePredictiveOutlook.DEGRADING
    )

    assert (
        report.high_risk_prediction_count
        == 2
    )

    assert (
        "2 predictive risk records"
        in report.executive_summary
    )


def test_health_score_is_calculated(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert 0 <= report.overall_health_score <= 100
    assert report.overall_health_score < 100


def test_source_bindings_match_store(
    tmp_path,
) -> None:
    report, store, _ = build_report(
        tmp_path
    )

    records = store.list_records()

    assert report.source_prediction_ids == tuple(
        record.prediction_id
        for record in records
    )

    assert report.source_record_hashes == tuple(
        record.record_hash
        for record in records
    )


def test_affected_link_is_extracted(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert (
        "link:buqayq-uqair:one"
        in report.affected_links
    )


def test_site_metadata_is_extracted(
    tmp_path,
) -> None:
    store, audit = make_source(
        tmp_path,
        count=1,
    )

    report = (
        build_executive_predictive_report(
            store=store,
            source_audit=audit,
            report_type="weekly",
            report_title="Weekly Report",
            generated_at=GENERATED_AT,
        )
    )

    assert report.prediction_count == 1


def test_key_findings_created(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert len(
        report.key_findings
    ) == 2

    assert all(
        "probability"
        in finding
        for finding in report.key_findings
    )


def test_high_risk_highlights_created(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert len(
        report.risk_highlights
    ) == 2

    assert all(
        "HIGH risk"
        in highlight
        for highlight
        in report.risk_highlights
    )


def test_priorities_created(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert report.recommended_priorities
    assert (
        "Prioritize investigation"
        in report.recommended_priorities[0]
    )


def test_builder_identity_in_metadata(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    assert report.generated_by == SERVICE_NAME

    assert (
        report.metadata[
            "builder_service"
        ]
        == SERVICE_NAME
    )

    assert (
        report.metadata["region"]
        == "Eastern Province"
    )


def test_empty_store_report(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path,
        count=0,
    )

    assert report.prediction_count == 0
    assert report.critical_prediction_count == 0
    assert report.high_risk_prediction_count == 0

    assert (
        report.overall_risk_class
        is ExecutivePredictiveRiskClass.LOW
    )

    assert (
        report.service_outlook
        is ExecutivePredictiveOutlook.STABLE
    )

    assert report.overall_health_score == 100.0
    assert report.key_findings == ()
    assert report.risk_highlights == ()


def test_invalid_audit_rejected(
    tmp_path,
) -> None:
    store, audit = make_source(
        tmp_path
    )

    object.__setattr__(
        audit,
        "record_hashes_valid",
        False,
    )

    with pytest.raises(
        ValueError,
        match="source_audit",
    ):
        build_executive_predictive_report(
            store=store,
            source_audit=audit,
            report_type="weekly",
            report_title="Invalid Report",
            generated_at=GENERATED_AT,
        )


def test_audit_count_mismatch_rejected(
    tmp_path,
) -> None:
    store, audit = make_source(
        tmp_path,
        count=1,
    )

    object.__setattr__(
        audit,
        "record_count",
        2,
    )

    with pytest.raises(
        ValueError,
        match="record count",
    ):
        build_executive_predictive_report(
            store=store,
            source_audit=audit,
            report_type="weekly",
            report_title="Invalid Report",
            generated_at=GENERATED_AT,
        )


def test_generated_before_report_end_rejected(
    tmp_path,
) -> None:
    store, audit = make_source(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="generated_at",
    ):
        build_executive_predictive_report(
            store=store,
            source_audit=audit,
            report_type="weekly",
            report_title="Invalid Report",
            generated_at=(
                NOW
                + timedelta(
                    minutes=30
                )
            ),
        )


def test_invalid_store_rejected(
    tmp_path,
) -> None:
    _, audit = make_source(
        tmp_path
    )

    builder = (
        ExecutivePredictiveReportBuilder()
    )

    with pytest.raises(
        TypeError,
        match="store",
    ):
        builder.build(
            store="invalid",
            source_audit=audit,
            report_type="weekly",
            report_title="Invalid",
            generated_at=GENERATED_AT,
        )


def test_invalid_audit_type_rejected(
    tmp_path,
) -> None:
    store, _ = make_source(
        tmp_path
    )

    builder = (
        ExecutivePredictiveReportBuilder()
    )

    with pytest.raises(
        TypeError,
        match="source_audit",
    ):
        builder.build(
            store=store,
            source_audit="invalid",
            report_type="weekly",
            report_title="Invalid",
            generated_at=GENERATED_AT,
        )


def test_naive_generated_at_rejected(
    tmp_path,
) -> None:
    store, audit = make_source(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_executive_predictive_report(
            store=store,
            source_audit=audit,
            report_type="weekly",
            report_title="Invalid",
            generated_at=datetime(
                2026,
                8,
                7,
                1,
                0,
            ),
        )


def test_report_never_grants_execution(
    tmp_path,
) -> None:
    report, _, _ = build_report(
        tmp_path
    )

    payload = report.to_dict()

    assert report.report_created is True
    assert report.pdf_rendered is False
    assert report.incident_created is False
    assert report.recommendation_executed is False
    assert report.decision_created is False
    assert report.authorization_created is False
    assert report.execution_allowed is False
    assert report.can_execute is False

    assert payload["can_execute"] is False
