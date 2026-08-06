from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from app.models.predictive_intelligence import (
    PredictiveIntelligenceType,
    PredictiveRiskClass,
    PredictiveSeverity,
    PredictiveState,
    PredictiveSubjectType,
)
from app.services.predictive_intelligence_validation import (
    PredictiveIntelligenceValidationResult,
    PredictiveIntelligenceValidator,
    validate_predictive_intelligence,
)
from tests.test_predictive_intelligence import (
    NOW,
    make_prediction,
)


VALIDATED_AT = (
    NOW
    + timedelta(
        minutes=2
    )
)


def mutate_frozen(
    prediction,
    field_name: str,
    value: Any,
):
    object.__setattr__(
        prediction,
        field_name,
        value,
    )

    return prediction


def validate(
    prediction,
):
    return validate_predictive_intelligence(
        prediction,
        validated_at=VALIDATED_AT,
    )


def test_valid_prediction_passes_validation() -> None:
    prediction = make_prediction()

    result = validate(
        prediction
    )

    assert isinstance(
        result,
        PredictiveIntelligenceValidationResult,
    )

    assert result.prediction_id == (
        prediction.prediction_id
    )

    assert result.validation_valid is True
    assert result.prediction_accepted is True
    assert result.validation_errors == ()

    assert result.fingerprint_valid is True
    assert result.prediction_window_valid is True
    assert result.subject_compatible is True
    assert result.state_transition_valid is True
    assert result.metric_direction_valid is True
    assert (
        result.probability_confidence_valid
        is True
    )
    assert result.risk_severity_valid is True
    assert result.evidence_sufficient is True
    assert result.model_identity_valid is True
    assert (
        result.temporal_consistency_valid
        is True
    )


def test_result_never_grants_execution() -> None:
    result = validate(
        make_prediction()
    )

    payload = result.to_dict()

    assert result.incident_created is False
    assert result.recommendation_created is False
    assert result.decision_created is False
    assert result.authorization_created is False
    assert result.approval_claim_created is False
    assert result.execution_lease_created is False
    assert result.execution_allowed is False
    assert result.can_execute is False

    assert payload["incident_created"] is False
    assert payload["decision_created"] is False
    assert payload["can_execute"] is False

    assert (
        payload["safety"][
            "predictive_validation_only"
        ]
        is True
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_tampered_fingerprint_rejected() -> None:
    prediction = make_prediction()

    mutate_frozen(
        prediction,
        "prediction_fingerprint",
        "f" * 64,
    )

    result = validate(
        prediction
    )

    assert result.fingerprint_valid is False
    assert result.validation_valid is False

    assert (
        "Prediction fingerprint is invalid"
        in result.validation_errors
    )


def test_incompatible_subject_rejected() -> None:
    prediction = make_prediction(
        prediction_type=(
            PredictiveIntelligenceType.DEVICE_FAILURE
        ),
        subject_type=(
            PredictiveSubjectType.LINK
        ),
        predicted_state=(
            PredictiveState.FAILED
        ),
        current_value=None,
        predicted_value=None,
        unit=None,
    )

    result = validate(
        prediction
    )

    assert result.subject_compatible is False
    assert result.validation_valid is False


@pytest.mark.parametrize(
    (
        "prediction_type",
        "subject_type",
    ),
    (
        (
            PredictiveIntelligenceType.DEVICE_FAILURE,
            PredictiveSubjectType.DEVICE,
        ),
        (
            PredictiveIntelligenceType.INTERFACE_FAILURE,
            PredictiveSubjectType.INTERFACE,
        ),
        (
            PredictiveIntelligenceType.LINK_DEGRADATION,
            PredictiveSubjectType.LINK,
        ),
        (
            PredictiveIntelligenceType.TRAFFIC_SPIKE,
            PredictiveSubjectType.SITE,
        ),
        (
            PredictiveIntelligenceType.SERVICE_OUTAGE,
            PredictiveSubjectType.SERVICE,
        ),
    ),
)
def test_compatible_subject_types_accepted(
    prediction_type,
    subject_type,
) -> None:
    predicted_state = (
        PredictiveState.FAILED
        if prediction_type
        in {
            PredictiveIntelligenceType.DEVICE_FAILURE,
            PredictiveIntelligenceType.INTERFACE_FAILURE,
            PredictiveIntelligenceType.SERVICE_OUTAGE,
        }
        else PredictiveState.DEGRADED
    )

    prediction = make_prediction(
        prediction_type=prediction_type,
        subject_type=subject_type,
        current_value=None,
        predicted_value=None,
        unit=None,
        predicted_state=predicted_state,
    )

    result = validate(
        prediction
    )

    assert result.subject_compatible is True


def test_invalid_state_transition_rejected() -> None:
    prediction = make_prediction(
        current_state=(
            PredictiveState.DEGRADED
        ),
        predicted_state=(
            PredictiveState.STABLE
        ),
    )

    result = validate(
        prediction
    )

    assert result.state_transition_valid is False
    assert result.validation_valid is False


def test_failure_prediction_requires_at_risk_or_failed() -> None:
    prediction = make_prediction(
        prediction_type=(
            PredictiveIntelligenceType.DEVICE_FAILURE
        ),
        subject_type=(
            PredictiveSubjectType.DEVICE
        ),
        current_state=(
            PredictiveState.STABLE
        ),
        predicted_state=(
            PredictiveState.DEGRADED
        ),
        current_value=None,
        predicted_value=None,
        unit=None,
    )

    result = validate(
        prediction
    )

    assert result.state_transition_valid is False


@pytest.mark.parametrize(
    (
        "prediction_type",
        "current_value",
        "predicted_value",
    ),
    (
        (
            PredictiveIntelligenceType.PACKET_LOSS_INCREASE,
            1.0,
            5.0,
        ),
        (
            PredictiveIntelligenceType.LATENCY_INCREASE,
            20.0,
            80.0,
        ),
        (
            PredictiveIntelligenceType.JITTER_INCREASE,
            2.0,
            12.0,
        ),
        (
            PredictiveIntelligenceType.TRAFFIC_SPIKE,
            100.0,
            500.0,
        ),
        (
            PredictiveIntelligenceType.THROUGHPUT_DECREASE,
            200.0,
            80.0,
        ),
        (
            PredictiveIntelligenceType.SIGNAL_DEGRADATION,
            -65.0,
            -82.0,
        ),
        (
            PredictiveIntelligenceType.AVAILABILITY_DECREASE,
            99.9,
            92.0,
        ),
    ),
)
def test_valid_metric_direction(
    prediction_type,
    current_value,
    predicted_value,
) -> None:
    prediction = make_prediction(
        prediction_type=prediction_type,
        current_value=current_value,
        predicted_value=predicted_value,
    )

    result = validate(
        prediction
    )

    assert result.metric_direction_valid is True


@pytest.mark.parametrize(
    (
        "prediction_type",
        "current_value",
        "predicted_value",
    ),
    (
        (
            PredictiveIntelligenceType.PACKET_LOSS_INCREASE,
            5.0,
            1.0,
        ),
        (
            PredictiveIntelligenceType.LATENCY_INCREASE,
            80.0,
            20.0,
        ),
        (
            PredictiveIntelligenceType.TRAFFIC_SPIKE,
            500.0,
            100.0,
        ),
        (
            PredictiveIntelligenceType.THROUGHPUT_DECREASE,
            80.0,
            200.0,
        ),
        (
            PredictiveIntelligenceType.SIGNAL_DEGRADATION,
            -82.0,
            -65.0,
        ),
        (
            PredictiveIntelligenceType.AVAILABILITY_DECREASE,
            92.0,
            99.9,
        ),
    ),
)
def test_invalid_metric_direction_rejected(
    prediction_type,
    current_value,
    predicted_value,
) -> None:
    prediction = make_prediction(
        prediction_type=prediction_type,
        current_value=current_value,
        predicted_value=predicted_value,
    )

    result = validate(
        prediction
    )

    assert result.metric_direction_valid is False
    assert result.validation_valid is False


def test_missing_one_metric_value_rejected() -> None:
    prediction = make_prediction()

    mutate_frozen(
        prediction,
        "predicted_value",
        None,
    )

    result = validate(
        prediction
    )

    assert result.metric_direction_valid is False


def test_high_risk_requires_probability_threshold() -> None:
    prediction = make_prediction(
        probability_percent=49,
    )

    result = validate(
        prediction
    )

    assert (
        result.probability_confidence_valid
        is False
    )

    assert result.validation_valid is False


def test_high_risk_requires_confidence_threshold() -> None:
    prediction = make_prediction(
        confidence_percent=49,
    )

    result = validate(
        prediction
    )

    assert (
        result.probability_confidence_valid
        is False
    )


@pytest.mark.parametrize(
    (
        "risk_class",
        "severity",
        "expected",
    ),
    (
        (
            PredictiveRiskClass.LOW,
            PredictiveSeverity.INFO,
            True,
        ),
        (
            PredictiveRiskClass.MEDIUM,
            PredictiveSeverity.WARNING,
            True,
        ),
        (
            PredictiveRiskClass.HIGH,
            PredictiveSeverity.MAJOR,
            True,
        ),
        (
            PredictiveRiskClass.CRITICAL,
            PredictiveSeverity.CRITICAL,
            True,
        ),
        (
            PredictiveRiskClass.LOW,
            PredictiveSeverity.CRITICAL,
            False,
        ),
        (
            PredictiveRiskClass.CRITICAL,
            PredictiveSeverity.INFO,
            False,
        ),
    ),
)
def test_risk_severity_consistency(
    risk_class,
    severity,
    expected,
) -> None:
    prediction = make_prediction(
        risk_class=risk_class,
        severity=severity,
    )

    result = validate(
        prediction
    )

    assert (
        result.risk_severity_valid
        is expected
    )


def test_high_risk_requires_two_evidence_items() -> None:
    prediction = make_prediction(
        evidence=(
            "Only one evidence item",
        ),
    )

    result = validate(
        prediction
    )

    assert result.evidence_sufficient is False
    assert result.validation_valid is False


def test_high_risk_requires_contributing_factor() -> None:
    prediction = make_prediction(
        contributing_factors=(),
    )

    result = validate(
        prediction
    )

    assert result.evidence_sufficient is False


def test_high_risk_requires_source_metric() -> None:
    prediction = make_prediction(
        source_metric_ids=(),
    )

    result = validate(
        prediction
    )

    assert result.evidence_sufficient is False


def test_medium_risk_requires_evidence() -> None:
    prediction = make_prediction(
        risk_class=(
            PredictiveRiskClass.MEDIUM
        ),
        severity=(
            PredictiveSeverity.WARNING
        ),
        evidence=(),
    )

    result = validate(
        prediction
    )

    assert result.evidence_sufficient is False


def test_low_risk_allows_empty_evidence() -> None:
    prediction = make_prediction(
        risk_class=(
            PredictiveRiskClass.LOW
        ),
        severity=(
            PredictiveSeverity.INFO
        ),
        evidence=(),
        contributing_factors=(),
        source_metric_ids=(),
    )

    result = validate(
        prediction
    )

    assert result.evidence_sufficient is True


def test_model_identity_tampering_detected() -> None:
    prediction = make_prediction()

    mutate_frozen(
        prediction,
        "model_name",
        "   ",
    )

    result = validate(
        prediction
    )

    assert result.model_identity_valid is False
    assert result.fingerprint_valid is False
    assert result.validation_valid is False


def test_validation_before_creation_rejected() -> None:
    prediction = make_prediction()

    result = validate_predictive_intelligence(
        prediction,
        validated_at=(
            prediction.created_at
            - timedelta(
                seconds=1
            )
        ),
    )

    assert (
        result.temporal_consistency_valid
        is False
    )

    assert result.validation_valid is False


def test_naive_validated_at_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        validate_predictive_intelligence(
            make_prediction(),
            validated_at=datetime(
                2026,
                8,
                6,
                22,
                50,
            ),
        )


def test_invalid_validated_at_type_rejected() -> None:
    validator = (
        PredictiveIntelligenceValidator()
    )

    with pytest.raises(
        TypeError,
        match="validated_at",
    ):
        validator.validate(
            prediction=make_prediction(),
            validated_at="invalid",
        )


def test_invalid_prediction_type_rejected() -> None:
    validator = (
        PredictiveIntelligenceValidator()
    )

    with pytest.raises(
        TypeError,
        match="prediction",
    ):
        validator.validate(
            prediction="invalid",
            validated_at=VALIDATED_AT,
        )


def test_multiple_failures_are_reported() -> None:
    prediction = make_prediction(
        prediction_type=(
            PredictiveIntelligenceType.DEVICE_FAILURE
        ),
        subject_type=(
            PredictiveSubjectType.LINK
        ),
        predicted_state=(
            PredictiveState.STABLE
        ),
        probability_percent=20,
        confidence_percent=20,
        evidence=(),
        contributing_factors=(),
        source_metric_ids=(),
        current_value=None,
        predicted_value=None,
        unit=None,
    )

    result = validate(
        prediction
    )

    assert result.validation_valid is False
    assert len(
        result.validation_errors
    ) >= 4


def test_service_identity_in_payload() -> None:
    payload = validate(
        make_prediction()
    ).to_dict()

    assert (
        payload["service"]["name"]
        ==
        "SS4TS Predictive Intelligence Validation"
    )

    assert (
        payload["service"]["version"]
        == "1.0.0"
    )
