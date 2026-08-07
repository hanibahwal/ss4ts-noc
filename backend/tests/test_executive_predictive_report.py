from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from app.models.executive_predictive_report import (
    ExecutivePredictiveOutlook,
    ExecutivePredictiveReport,
    ExecutivePredictiveReportType,
    ExecutivePredictiveRiskClass,
)


PERIOD_START = datetime(
    2026,
    8,
    1,
    0,
    0,
    tzinfo=timezone.utc,
)

PERIOD_END = datetime(
    2026,
    8,
    7,
    0,
    0,
    tzinfo=timezone.utc,
)

GENERATED_AT = (
    PERIOD_END
    + timedelta(
        minutes=5
    )
)


def make_report(
    **overrides,
) -> ExecutivePredictiveReport:
    values = {
        "report_id":
            "executive-predictive-report:test:1",
        "report_type":
            ExecutivePredictiveReportType.WEEKLY,
        "report_title":
            "Weekly Predictive Risk Report",
        "report_period_start":
            PERIOD_START,
        "report_period_end":
            PERIOD_END,
        "generated_at":
            GENERATED_AT,
        "executive_summary":
            (
                "Two high-risk links require "
                "executive attention."
            ),
        "overall_risk_class":
            ExecutivePredictiveRiskClass.HIGH,
        "overall_health_score":
            78.5,
        "service_outlook":
            ExecutivePredictiveOutlook.WATCH,
        "prediction_count":
            3,
        "critical_prediction_count":
            1,
        "high_risk_prediction_count":
            1,
        "affected_sites": (
            "Buqayq",
            "Al-Uqair",
            "Buqayq",
        ),
        "affected_devices": (
            "AF-5XHD-01",
        ),
        "affected_links": (
            "link:buqayq-uqair",
        ),
        "affected_services": (
            "camp-internet",
        ),
        "key_findings": (
            "Evening signal degradation detected",
            "Capacity utilization is increasing",
        ),
        "risk_highlights": (
            "One critical outage prediction",
            "One high-risk degradation prediction",
        ),
        "capacity_forecast": (
            "Peak utilization may exceed 90%",
        ),
        "recommended_priorities": (
            "Review the affected wireless link",
            "Prepare additional capacity",
        ),
        "source_prediction_ids": (
            "prediction:1",
            "prediction:2",
            "prediction:3",
        ),
        "source_record_hashes": (
            "a" * 64,
            "b" * 64,
            "c" * 64,
        ),
        "source_audit_id":
            "predictive-store-audit:test:1",
        "source_audit_valid":
            True,
        "generated_by":
            "ss4ts-executive-report-builder",
        "schema_version":
            "1.0",
        "metadata": {
            "region": "Eastern Province",
        },
        "report_fingerprint":
            "",
    }

    values.update(
        overrides
    )

    return ExecutivePredictiveReport(
        **values
    )


def test_create_executive_predictive_report() -> None:
    report = make_report()

    assert (
        report.report_type
        is ExecutivePredictiveReportType.WEEKLY
    )

    assert (
        report.overall_risk_class
        is ExecutivePredictiveRiskClass.HIGH
    )

    assert report.overall_health_score == 78.5
    assert report.prediction_count == 3

    assert (
        report.report_fingerprint
        == report.calculate_fingerprint()
    )


def test_string_enums_are_normalized() -> None:
    report = make_report(
        report_type="monthly",
        overall_risk_class="critical",
        service_outlook="degrading",
    )

    assert (
        report.report_type
        is ExecutivePredictiveReportType.MONTHLY
    )

    assert (
        report.overall_risk_class
        is ExecutivePredictiveRiskClass.CRITICAL
    )

    assert (
        report.service_outlook
        is ExecutivePredictiveOutlook.DEGRADING
    )


def test_report_is_immutable() -> None:
    report = make_report()

    with pytest.raises(
        FrozenInstanceError,
    ):
        report.report_title = "Changed"


def test_duplicate_values_are_removed() -> None:
    report = make_report()

    assert report.affected_sites == (
        "Buqayq",
        "Al-Uqair",
    )


def test_to_dict_contains_safety_contract() -> None:
    payload = make_report().to_dict()

    assert payload["report_created"] is True
    assert payload["pdf_rendered"] is False
    assert payload["incident_created"] is False
    assert (
        payload["recommendation_executed"]
        is False
    )
    assert payload["decision_created"] is False
    assert (
        payload["authorization_created"]
        is False
    )
    assert payload["execution_allowed"] is False
    assert payload["can_execute"] is False

    assert (
        payload["safety"][
            "executive_reporting_only"
        ]
        is True
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "report_period_start",
        "report_period_end",
        "generated_at",
    ),
)
def test_naive_datetime_rejected(
    field_name,
) -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        make_report(
            **{
                field_name:
                    datetime(
                        2026,
                        8,
                        7,
                        0,
                        0,
                    ),
            }
        )


def test_invalid_period_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="report_period_end",
    ):
        make_report(
            report_period_end=PERIOD_START
        )


def test_generated_before_period_end_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="generated_at",
    ):
        make_report(
            generated_at=(
                PERIOD_END
                - timedelta(
                    seconds=1
                )
            )
        )


@pytest.mark.parametrize(
    "score",
    (
        -0.1,
        100.1,
        float("inf"),
    ),
)
def test_invalid_health_score_rejected(
    score,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        make_report(
            overall_health_score=score
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "prediction_count",
        "critical_prediction_count",
        "high_risk_prediction_count",
    ),
)
def test_negative_counts_rejected(
    field_name,
) -> None:
    with pytest.raises(
        ValueError,
        match="non-negative integer",
    ):
        make_report(
            **{
                field_name: -1,
            }
        )


def test_critical_count_cannot_exceed_total() -> None:
    with pytest.raises(
        ValueError,
        match="critical_prediction_count",
    ):
        make_report(
            prediction_count=3,
            critical_prediction_count=4,
        )


def test_combined_risk_counts_cannot_exceed_total() -> None:
    with pytest.raises(
        ValueError,
        match="critical and high-risk",
    ):
        make_report(
            prediction_count=3,
            critical_prediction_count=2,
            high_risk_prediction_count=2,
        )


def test_prediction_count_matches_sources() -> None:
    with pytest.raises(
        ValueError,
        match="prediction_count",
    ):
        make_report(
            prediction_count=2
        )


def test_source_hash_count_matches_predictions() -> None:
    with pytest.raises(
        ValueError,
        match="source_record_hashes",
    ):
        make_report(
            source_record_hashes=(
                "a" * 64,
            )
        )


def test_invalid_source_audit_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="source_audit_valid",
    ):
        make_report(
            source_audit_valid=False
        )


def test_report_with_predictions_requires_findings() -> None:
    with pytest.raises(
        ValueError,
        match="key_findings",
    ):
        make_report(
            key_findings=()
        )


def test_high_risk_report_requires_highlights() -> None:
    with pytest.raises(
        ValueError,
        match="risk_highlights",
    ):
        make_report(
            risk_highlights=()
        )


def test_low_risk_report_allows_empty_highlights() -> None:
    report = make_report(
        overall_risk_class=(
            ExecutivePredictiveRiskClass.LOW
        ),
        critical_prediction_count=0,
        high_risk_prediction_count=0,
        risk_highlights=(),
    )

    assert report.risk_highlights == ()


def test_empty_report_is_supported() -> None:
    report = make_report(
        overall_risk_class=(
            ExecutivePredictiveRiskClass.LOW
        ),
        service_outlook=(
            ExecutivePredictiveOutlook.STABLE
        ),
        prediction_count=0,
        critical_prediction_count=0,
        high_risk_prediction_count=0,
        source_prediction_ids=(),
        source_record_hashes=(),
        key_findings=(),
        risk_highlights=(),
    )

    assert report.prediction_count == 0


def test_fingerprint_is_deterministic() -> None:
    first = make_report()
    second = make_report()

    assert (
        first.report_fingerprint
        == second.report_fingerprint
    )


def test_changed_report_changes_fingerprint() -> None:
    first = make_report()

    second = make_report(
        overall_health_score=65.0
    )

    assert (
        first.report_fingerprint
        != second.report_fingerprint
    )


def test_fingerprint_mismatch_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="report_fingerprint mismatch",
    ):
        make_report(
            report_fingerprint="f" * 64
        )


def test_invalid_fingerprint_format_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="SHA-256",
    ):
        make_report(
            report_fingerprint="invalid"
        )


def test_reconstruction_preserves_fingerprint() -> None:
    report = make_report()

    reconstructed = replace(
        report,
        report_fingerprint=(
            report.report_fingerprint
        ),
    )

    assert (
        reconstructed.report_fingerprint
        == report.report_fingerprint
    )


def test_properties_never_grant_execution() -> None:
    report = make_report()

    assert report.report_created is True
    assert report.pdf_rendered is False
    assert report.incident_created is False
    assert report.recommendation_executed is False
    assert report.decision_created is False
    assert report.authorization_created is False
    assert report.execution_allowed is False
    assert report.can_execute is False


def test_metadata_must_be_dictionary() -> None:
    with pytest.raises(
        TypeError,
        match="metadata must be a dictionary",
    ):
        make_report(
            metadata="invalid"
        )


def test_invalid_enum_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="report_type is unsupported",
    ):
        make_report(
            report_type="execute_now"
        )
