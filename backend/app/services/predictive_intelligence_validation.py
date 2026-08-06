from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.predictive_intelligence import (
    PredictiveIntelligence,
    PredictiveIntelligenceType,
    PredictiveRiskClass,
    PredictiveSeverity,
    PredictiveState,
    PredictiveSubjectType,
)


SERVICE_NAME = (
    "SS4TS Predictive Intelligence Validation"
)

SERVICE_VERSION = "1.0.0"


RISK_RANK = {
    PredictiveRiskClass.LOW: 1,
    PredictiveRiskClass.MEDIUM: 2,
    PredictiveRiskClass.HIGH: 3,
    PredictiveRiskClass.CRITICAL: 4,
}


SEVERITY_RANK = {
    PredictiveSeverity.INFO: 1,
    PredictiveSeverity.WARNING: 2,
    PredictiveSeverity.MAJOR: 3,
    PredictiveSeverity.CRITICAL: 4,
}


STATE_RANK = {
    PredictiveState.UNKNOWN: 0,
    PredictiveState.STABLE: 1,
    PredictiveState.DEGRADED: 2,
    PredictiveState.AT_RISK: 3,
    PredictiveState.FAILED: 4,
}


ALLOWED_SUBJECT_TYPES = {
    PredictiveIntelligenceType.LINK_DEGRADATION: {
        PredictiveSubjectType.LINK,
    },
    PredictiveIntelligenceType.CAPACITY_EXHAUSTION: {
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
    PredictiveIntelligenceType.DEVICE_FAILURE: {
        PredictiveSubjectType.DEVICE,
    },
    PredictiveIntelligenceType.INTERFACE_FAILURE: {
        PredictiveSubjectType.INTERFACE,
    },
    PredictiveIntelligenceType.PACKET_LOSS_INCREASE: {
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
    PredictiveIntelligenceType.LATENCY_INCREASE: {
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
    PredictiveIntelligenceType.JITTER_INCREASE: {
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
    PredictiveIntelligenceType.THROUGHPUT_DECREASE: {
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
    PredictiveIntelligenceType.SIGNAL_DEGRADATION: {
        PredictiveSubjectType.DEVICE,
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
    },
    PredictiveIntelligenceType.SERVICE_OUTAGE: {
        PredictiveSubjectType.DEVICE,
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
    PredictiveIntelligenceType.TRAFFIC_SPIKE: {
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
    PredictiveIntelligenceType.AVAILABILITY_DECREASE: {
        PredictiveSubjectType.DEVICE,
        PredictiveSubjectType.INTERFACE,
        PredictiveSubjectType.LINK,
        PredictiveSubjectType.SITE,
        PredictiveSubjectType.SERVICE,
        PredictiveSubjectType.NETWORK,
    },
}


INCREASE_TYPES = {
    PredictiveIntelligenceType.PACKET_LOSS_INCREASE,
    PredictiveIntelligenceType.LATENCY_INCREASE,
    PredictiveIntelligenceType.JITTER_INCREASE,
    PredictiveIntelligenceType.TRAFFIC_SPIKE,
    PredictiveIntelligenceType.CAPACITY_EXHAUSTION,
}


DECREASE_TYPES = {
    PredictiveIntelligenceType.THROUGHPUT_DECREASE,
    PredictiveIntelligenceType.SIGNAL_DEGRADATION,
    PredictiveIntelligenceType.AVAILABILITY_DECREASE,
}


FAILURE_TYPES = {
    PredictiveIntelligenceType.DEVICE_FAILURE,
    PredictiveIntelligenceType.INTERFACE_FAILURE,
    PredictiveIntelligenceType.SERVICE_OUTAGE,
}


@dataclass(
    frozen=True,
    slots=True,
)
class PredictiveIntelligenceValidationResult:
    prediction_id: str

    validation_valid: bool
    validation_errors: tuple[str, ...]

    fingerprint_valid: bool
    prediction_window_valid: bool
    subject_compatible: bool
    state_transition_valid: bool
    metric_direction_valid: bool
    probability_confidence_valid: bool
    risk_severity_valid: bool
    evidence_sufficient: bool
    model_identity_valid: bool
    temporal_consistency_valid: bool

    validated_at: datetime

    @property
    def prediction_accepted(
        self,
    ) -> bool:
        return self.validation_valid

    @property
    def incident_created(
        self,
    ) -> bool:
        return False

    @property
    def recommendation_created(
        self,
    ) -> bool:
        return False

    @property
    def decision_created(
        self,
    ) -> bool:
        return False

    @property
    def authorization_created(
        self,
    ) -> bool:
        return False

    @property
    def approval_claim_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_lease_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_allowed(
        self,
    ) -> bool:
        return False

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "prediction_id":
                self.prediction_id,
            "validation_valid":
                self.validation_valid,
            "prediction_accepted":
                self.prediction_accepted,
            "validation_errors":
                list(
                    self.validation_errors
                ),
            "checks": {
                "fingerprint_valid":
                    self.fingerprint_valid,
                "prediction_window_valid":
                    self.prediction_window_valid,
                "subject_compatible":
                    self.subject_compatible,
                "state_transition_valid":
                    self.state_transition_valid,
                "metric_direction_valid":
                    self.metric_direction_valid,
                "probability_confidence_valid":
                    self.probability_confidence_valid,
                "risk_severity_valid":
                    self.risk_severity_valid,
                "evidence_sufficient":
                    self.evidence_sufficient,
                "model_identity_valid":
                    self.model_identity_valid,
                "temporal_consistency_valid":
                    self.temporal_consistency_valid,
            },
            "validated_at":
                self.validated_at.isoformat(),
            "incident_created":
                False,
            "recommendation_created":
                False,
            "decision_created":
                False,
            "authorization_created":
                False,
            "approval_claim_created":
                False,
            "execution_lease_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "predictive_validation_only":
                    True,
                "read_only_validation":
                    True,
                "prediction_execution_authority":
                    False,
                "incident_created":
                    False,
                "recommendation_created":
                    False,
                "decision_created":
                    False,
                "authorization_created":
                    False,
                "authorization_approved":
                    False,
                "authorization_token_created":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
                    False,
                "execution_allowed":
                    False,
                "execution_approved":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_access_performed":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            },
        }


class PredictiveIntelligenceValidator:
    @staticmethod
    def _normalize_validated_at(
        validated_at: datetime | None,
    ) -> datetime:
        value = (
            validated_at
            or datetime.now(
                timezone.utc
            )
        )

        if not isinstance(
            value,
            datetime,
        ):
            raise TypeError(
                "validated_at must be a datetime"
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "validated_at must be timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )

    @staticmethod
    def _validate_fingerprint(
        prediction: PredictiveIntelligence,
    ) -> bool:
        try:
            return (
                prediction.prediction_fingerprint
                == prediction.calculate_fingerprint()
            )
        except (
            TypeError,
            ValueError,
            AttributeError,
        ):
            return False

    @staticmethod
    def _validate_prediction_window(
        prediction: PredictiveIntelligence,
    ) -> bool:
        return (
            prediction.prediction_window_start
            >= prediction.observed_at
            and prediction.prediction_window_end
            > prediction.prediction_window_start
        )

    @staticmethod
    def _validate_subject_compatibility(
        prediction: PredictiveIntelligence,
    ) -> bool:
        allowed = ALLOWED_SUBJECT_TYPES.get(
            prediction.prediction_type,
            set(),
        )

        return (
            prediction.subject_type
            in allowed
        )

    @staticmethod
    def _validate_state_transition(
        prediction: PredictiveIntelligence,
    ) -> bool:
        if (
            prediction.prediction_type
            in FAILURE_TYPES
        ):
            return (
                prediction.predicted_state
                in {
                    PredictiveState.AT_RISK,
                    PredictiveState.FAILED,
                }
                and STATE_RANK[
                    prediction.predicted_state
                ]
                >= STATE_RANK[
                    prediction.current_state
                ]
            )

        return (
            STATE_RANK[
                prediction.predicted_state
            ]
            >= STATE_RANK[
                prediction.current_state
            ]
        )

    @staticmethod
    def _validate_metric_direction(
        prediction: PredictiveIntelligence,
    ) -> bool:
        current_value = (
            prediction.current_value
        )
        predicted_value = (
            prediction.predicted_value
        )

        if (
            current_value is None
            and predicted_value is None
        ):
            return True

        if (
            current_value is None
            or predicted_value is None
        ):
            return False

        if (
            prediction.prediction_type
            in INCREASE_TYPES
        ):
            return (
                predicted_value
                > current_value
            )

        if (
            prediction.prediction_type
            in DECREASE_TYPES
        ):
            return (
                predicted_value
                < current_value
            )

        if (
            prediction.prediction_type
            is
            PredictiveIntelligenceType.LINK_DEGRADATION
        ):
            return (
                predicted_value
                != current_value
            )

        return True

    @staticmethod
    def _validate_probability_confidence(
        prediction: PredictiveIntelligence,
    ) -> bool:
        probability = (
            prediction.probability_percent
        )
        confidence = (
            prediction.confidence_percent
        )

        if (
            prediction.risk_class
            in {
                PredictiveRiskClass.HIGH,
                PredictiveRiskClass.CRITICAL,
            }
        ):
            return (
                probability >= 50
                and confidence >= 50
            )

        return True

    @staticmethod
    def _validate_risk_severity(
        prediction: PredictiveIntelligence,
    ) -> bool:
        risk_rank = RISK_RANK[
            prediction.risk_class
        ]

        severity_rank = SEVERITY_RANK[
            prediction.severity
        ]

        return (
            abs(
                risk_rank
                - severity_rank
            )
            <= 1
        )

    @staticmethod
    def _validate_evidence(
        prediction: PredictiveIntelligence,
    ) -> bool:
        evidence_count = len(
            prediction.evidence
        )

        factor_count = len(
            prediction.contributing_factors
        )

        if (
            prediction.risk_class
            in {
                PredictiveRiskClass.HIGH,
                PredictiveRiskClass.CRITICAL,
            }
        ):
            return (
                evidence_count >= 2
                and factor_count >= 1
                and len(
                    prediction.source_metric_ids
                )
                >= 1
            )

        if (
            prediction.risk_class
            is PredictiveRiskClass.MEDIUM
        ):
            return evidence_count >= 1

        return True

    @staticmethod
    def _validate_model_identity(
        prediction: PredictiveIntelligence,
    ) -> bool:
        return (
            bool(
                prediction.model_name.strip()
            )
            and bool(
                prediction.model_version.strip()
            )
        )

    @staticmethod
    def _validate_temporal_consistency(
        prediction: PredictiveIntelligence,
        *,
        validated_at: datetime,
    ) -> bool:
        return (
            prediction.created_at
            >= prediction.observed_at
            and validated_at
            >= prediction.created_at
        )

    def validate(
        self,
        *,
        prediction: PredictiveIntelligence,
        validated_at: datetime | None = None,
    ) -> PredictiveIntelligenceValidationResult:
        if not isinstance(
            prediction,
            PredictiveIntelligence,
        ):
            raise TypeError(
                "prediction must be a "
                "PredictiveIntelligence"
            )

        resolved_validated_at = (
            self._normalize_validated_at(
                validated_at
            )
        )

        errors: list[str] = []

        fingerprint_valid = (
            self._validate_fingerprint(
                prediction
            )
        )

        if not fingerprint_valid:
            errors.append(
                "Prediction fingerprint is invalid"
            )

        prediction_window_valid = (
            self._validate_prediction_window(
                prediction
            )
        )

        if not prediction_window_valid:
            errors.append(
                "Prediction window is invalid"
            )

        subject_compatible = (
            self._validate_subject_compatibility(
                prediction
            )
        )

        if not subject_compatible:
            errors.append(
                "Prediction subject is incompatible "
                "with prediction type"
            )

        state_transition_valid = (
            self._validate_state_transition(
                prediction
            )
        )

        if not state_transition_valid:
            errors.append(
                "Predicted state transition is invalid"
            )

        metric_direction_valid = (
            self._validate_metric_direction(
                prediction
            )
        )

        if not metric_direction_valid:
            errors.append(
                "Predicted metric direction is invalid"
            )

        probability_confidence_valid = (
            self._validate_probability_confidence(
                prediction
            )
        )

        if not probability_confidence_valid:
            errors.append(
                "Prediction probability or confidence "
                "is insufficient for its risk class"
            )

        risk_severity_valid = (
            self._validate_risk_severity(
                prediction
            )
        )

        if not risk_severity_valid:
            errors.append(
                "Prediction risk and severity "
                "are inconsistent"
            )

        evidence_sufficient = (
            self._validate_evidence(
                prediction
            )
        )

        if not evidence_sufficient:
            errors.append(
                "Prediction evidence is insufficient"
            )

        model_identity_valid = (
            self._validate_model_identity(
                prediction
            )
        )

        if not model_identity_valid:
            errors.append(
                "Prediction model identity is invalid"
            )

        temporal_consistency_valid = (
            self._validate_temporal_consistency(
                prediction,
                validated_at=(
                    resolved_validated_at
                ),
            )
        )

        if not temporal_consistency_valid:
            errors.append(
                "Prediction temporal consistency "
                "is invalid"
            )

        validation_valid = all(
            (
                fingerprint_valid,
                prediction_window_valid,
                subject_compatible,
                state_transition_valid,
                metric_direction_valid,
                probability_confidence_valid,
                risk_severity_valid,
                evidence_sufficient,
                model_identity_valid,
                temporal_consistency_valid,
                not errors,
            )
        )

        return PredictiveIntelligenceValidationResult(
            prediction_id=(
                prediction.prediction_id
            ),
            validation_valid=(
                validation_valid
            ),
            validation_errors=tuple(
                errors
            ),
            fingerprint_valid=(
                fingerprint_valid
            ),
            prediction_window_valid=(
                prediction_window_valid
            ),
            subject_compatible=(
                subject_compatible
            ),
            state_transition_valid=(
                state_transition_valid
            ),
            metric_direction_valid=(
                metric_direction_valid
            ),
            probability_confidence_valid=(
                probability_confidence_valid
            ),
            risk_severity_valid=(
                risk_severity_valid
            ),
            evidence_sufficient=(
                evidence_sufficient
            ),
            model_identity_valid=(
                model_identity_valid
            ),
            temporal_consistency_valid=(
                temporal_consistency_valid
            ),
            validated_at=(
                resolved_validated_at
            ),
        )


def validate_predictive_intelligence(
    prediction: PredictiveIntelligence,
    *,
    validated_at: datetime | None = None,
) -> PredictiveIntelligenceValidationResult:
    return (
        PredictiveIntelligenceValidator()
        .validate(
            prediction=prediction,
            validated_at=validated_at,
        )
    )
