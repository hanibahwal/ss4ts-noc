from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from app.models.predictive_intelligence import (
    PredictiveIntelligence,
    PredictiveIntelligenceType,
    PredictiveRiskClass,
    PredictiveSeverity,
    PredictiveState,
    PredictiveSubjectType,
)


NOW = datetime(
    2026,
    8,
    6,
    22,
    45,
    tzinfo=timezone.utc,
)


def make_prediction(
    **overrides,
) -> PredictiveIntelligence:
    values = {
        "prediction_id":
            "predictive-intelligence:test:1",
        "prediction_type":
            PredictiveIntelligenceType.LINK_DEGRADATION,
        "subject_type":
            PredictiveSubjectType.LINK,
        "subject_id":
            "link:buqayq-uqair:1",
        "observed_at":
            NOW,
        "prediction_window_start":
            NOW
            + timedelta(
                minutes=5
            ),
        "prediction_window_end":
            NOW
            + timedelta(
                hours=1
            ),
        "current_state":
            PredictiveState.STABLE,
        "predicted_state":
            PredictiveState.DEGRADED,
        "current_value":
            -65.2,
        "predicted_value":
            -82.4,
        "unit":
            "dBm",
        "confidence_percent":
            92.5,
        "probability_percent":
            87.0,
        "risk_class":
            PredictiveRiskClass.HIGH,
        "severity":
            PredictiveSeverity.MAJOR,
        "evidence": (
            "Signal trend decreased by 12 dB",
            "Packet loss increased",
            "Signal trend decreased by 12 dB",
        ),
        "contributing_factors": (
            "Evening interference",
            "Link fade",
        ),
        "model_name":
            "ss4ts-link-degradation-model",
        "model_version":
            "1.0.0",
        "source_metric_ids": (
            "metric:signal:1",
            "metric:packet-loss:1",
        ),
        "metadata": {
            "site": "Buqayq",
            "frequency_mhz": 5800,
        },
        "created_at":
            NOW
            + timedelta(
                seconds=1
            ),
        "prediction_fingerprint":
            "",
    }

    values.update(
        overrides
    )

    return PredictiveIntelligence(
        **values
    )


def test_create_predictive_intelligence() -> None:
    prediction = make_prediction()

    assert (
        prediction.prediction_type
        is
        PredictiveIntelligenceType.LINK_DEGRADATION
    )

    assert (
        prediction.subject_type
        is PredictiveSubjectType.LINK
    )

    assert (
        prediction.current_state
        is PredictiveState.STABLE
    )

    assert (
        prediction.predicted_state
        is PredictiveState.DEGRADED
    )

    assert prediction.confidence_percent == 92.5
    assert prediction.probability_percent == 87.0

    assert (
        prediction.prediction_fingerprint
        == prediction.calculate_fingerprint()
    )


def test_string_enums_are_normalized() -> None:
    prediction = make_prediction(
        prediction_type="traffic_spike",
        subject_type="site",
        current_state="stable",
        predicted_state="at_risk",
        risk_class="critical",
        severity="critical",
    )

    assert (
        prediction.prediction_type
        is PredictiveIntelligenceType.TRAFFIC_SPIKE
    )

    assert (
        prediction.subject_type
        is PredictiveSubjectType.SITE
    )

    assert (
        prediction.predicted_state
        is PredictiveState.AT_RISK
    )

    assert (
        prediction.risk_class
        is PredictiveRiskClass.CRITICAL
    )


def test_prediction_is_immutable() -> None:
    prediction = make_prediction()

    with pytest.raises(
        FrozenInstanceError,
    ):
        prediction.subject_id = "changed"


def test_duplicate_evidence_is_removed() -> None:
    prediction = make_prediction()

    assert prediction.evidence == (
        "Signal trend decreased by 12 dB",
        "Packet loss increased",
    )


def test_to_dict_contains_safety_contract() -> None:
    prediction = make_prediction()

    payload = prediction.to_dict()

    assert payload["prediction_created"] is True
    assert payload["incident_created"] is False
    assert (
        payload["recommendation_created"]
        is False
    )
    assert payload["decision_created"] is False
    assert (
        payload["authorization_created"]
        is False
    )
    assert (
        payload["approval_claim_created"]
        is False
    )
    assert (
        payload["execution_lease_created"]
        is False
    )
    assert payload["execution_allowed"] is False
    assert payload["can_execute"] is False

    assert (
        payload["safety"][
            "predictive_analysis_only"
        ]
        is True
    )

    assert (
        payload["safety"][
            "network_io_performed"
        ]
        is False
    )


@pytest.mark.parametrize(
    (
        "field_name",
        "field_value",
    ),
    (
        (
            "confidence_percent",
            -0.1,
        ),
        (
            "confidence_percent",
            100.1,
        ),
        (
            "probability_percent",
            -1,
        ),
        (
            "probability_percent",
            101,
        ),
    ),
)
def test_invalid_percentages_rejected(
    field_name,
    field_value,
) -> None:
    with pytest.raises(
        ValueError,
        match="between 0 and 100",
    ):
        make_prediction(
            **{
                field_name:
                    field_value,
            }
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "observed_at",
        "prediction_window_start",
        "prediction_window_end",
        "created_at",
    ),
)
def test_naive_datetimes_rejected(
    field_name,
) -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        make_prediction(
            **{
                field_name:
                    datetime(
                        2026,
                        8,
                        6,
                        22,
                        45,
                    ),
            }
        )


def test_prediction_start_before_observation_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="prediction_window_start",
    ):
        make_prediction(
            prediction_window_start=(
                NOW
                - timedelta(
                    seconds=1
                )
            )
        )


def test_invalid_prediction_window_rejected() -> None:
    start = (
        NOW
        + timedelta(
            minutes=5
        )
    )

    with pytest.raises(
        ValueError,
        match="prediction_window_end",
    ):
        make_prediction(
            prediction_window_start=start,
            prediction_window_end=start,
        )


def test_created_before_observation_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="created_at",
    ):
        make_prediction(
            created_at=(
                NOW
                - timedelta(
                    seconds=1
                )
            )
        )


def test_numeric_value_requires_unit() -> None:
    with pytest.raises(
        ValueError,
        match="unit is required",
    ):
        make_prediction(
            unit=None
        )


def test_prediction_without_numeric_values_allows_no_unit() -> None:
    prediction = make_prediction(
        current_value=None,
        predicted_value=None,
        unit=None,
    )

    assert prediction.current_value is None
    assert prediction.predicted_value is None
    assert prediction.unit is None


def test_invalid_enum_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="prediction_type is unsupported",
    ):
        make_prediction(
            prediction_type="execute_command"
        )


def test_fingerprint_is_deterministic() -> None:
    first = make_prediction()
    second = make_prediction()

    assert (
        first.prediction_fingerprint
        == second.prediction_fingerprint
    )


def test_changed_prediction_changes_fingerprint() -> None:
    first = make_prediction()

    second = make_prediction(
        predicted_value=-90.0
    )

    assert (
        first.prediction_fingerprint
        != second.prediction_fingerprint
    )


def test_fingerprint_mismatch_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="prediction_fingerprint mismatch",
    ):
        make_prediction(
            prediction_fingerprint="f" * 64
        )


def test_invalid_fingerprint_format_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="SHA-256",
    ):
        make_prediction(
            prediction_fingerprint="invalid"
        )


def test_properties_never_grant_execution() -> None:
    prediction = make_prediction()

    assert prediction.prediction_created is True
    assert prediction.incident_created is False
    assert (
        prediction.recommendation_created
        is False
    )
    assert prediction.decision_created is False
    assert prediction.authorization_created is False
    assert prediction.approval_claim_created is False
    assert prediction.execution_lease_created is False
    assert prediction.execution_allowed is False
    assert prediction.can_execute is False


def test_metadata_must_be_dictionary() -> None:
    with pytest.raises(
        TypeError,
        match="metadata must be a dictionary",
    ):
        make_prediction(
            metadata="invalid"
        )


def test_non_finite_numeric_values_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="finite",
    ):
        make_prediction(
            predicted_value=float(
                "inf"
            )
        )


def test_reconstructed_prediction_preserves_fingerprint() -> None:
    prediction = make_prediction()

    reconstructed = replace(
        prediction,
        prediction_fingerprint=(
            prediction.prediction_fingerprint
        ),
    )

    assert (
        reconstructed.prediction_fingerprint
        == prediction.prediction_fingerprint
    )
