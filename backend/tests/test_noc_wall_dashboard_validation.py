from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest

from app.services.noc_wall_dashboard_validation import (
    NOCWallDashboardValidationResult,
    NOCWallDashboardValidator,
    VALIDATOR_SERVICE_NAME,
    validate_noc_wall_dashboard_snapshot,
)
from tests.test_noc_wall_dashboard_builder import (
    GENERATED_AT,
    build_snapshot,
)


VALIDATED_AT = (
    GENERATED_AT
    + timedelta(
        minutes=5
    )
)


def validate_snapshot(
    tmp_path,
):
    snapshot, store, record, state = (
        build_snapshot(
            tmp_path
        )
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    return (
        result,
        snapshot,
        store,
        record,
        state,
    )


def test_valid_snapshot_is_accepted(
    tmp_path,
) -> None:
    result, snapshot, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    assert isinstance(
        result,
        NOCWallDashboardValidationResult,
    )

    assert result.validation_valid is True
    assert result.dashboard_accepted is True
    assert result.validation_errors == ()

    assert result.dashboard_id == (
        snapshot.dashboard_id
    )

    assert (
        result.dashboard_fingerprint
        == snapshot.dashboard_fingerprint
    )

    assert all(
        result.checks.values()
    )


def test_validation_identity(
    tmp_path,
) -> None:
    result, *_ = validate_snapshot(
        tmp_path
    )

    assert result.validator_name == (
        VALIDATOR_SERVICE_NAME
    )

    assert result.validator_version == "1.0.0"

    assert result.validation_id.startswith(
        "noc-wall-dashboard-validation:"
    )


def test_validation_is_deterministic(
    tmp_path,
) -> None:
    result, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    second = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    assert (
        result.validation_id
        == second.validation_id
    )

    assert (
        result.to_dict()
        == second.to_dict()
    )


def test_validation_does_not_mutate_snapshot(
    tmp_path,
) -> None:
    result, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    before = snapshot.to_dict()

    second = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    after = snapshot.to_dict()

    assert result.validation_valid is True
    assert second.validation_valid is True
    assert before == after


def test_validation_never_grants_execution(
    tmp_path,
) -> None:
    result, *_ = validate_snapshot(
        tmp_path
    )

    payload = result.to_dict()

    assert result.incident_created is False
    assert result.recommendation_executed is False
    assert result.decision_created is False
    assert result.authorization_created is False
    assert result.execution_allowed is False
    assert result.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["validation_only"]
        is True
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_tampered_fingerprint_is_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    object.__setattr__(
        snapshot,
        "dashboard_fingerprint",
        "f" * 64,
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    assert result.validation_valid is False
    assert result.dashboard_accepted is False

    assert (
        result.checks["fingerprint_valid"]
        is False
    )


def test_builder_identity_tampering_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    object.__setattr__(
        snapshot,
        "generated_by",
        "Unknown Builder",
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    assert result.validation_valid is False

    assert (
        result.checks[
            "builder_identity_valid"
        ]
        is False
    )


def test_latest_report_id_tampering_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    object.__setattr__(
        snapshot,
        "latest_report_id",
        "executive-predictive-report:tampered",
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    assert result.validation_valid is False

    assert (
        result.checks[
            "latest_report_bindings_valid"
        ]
        is False
    )


def test_latest_report_fingerprint_tampering_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    object.__setattr__(
        snapshot,
        "latest_report_fingerprint",
        "e" * 64,
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    assert result.validation_valid is False

    assert (
        result.checks[
            "latest_report_bindings_valid"
        ]
        is False
    )


def test_prediction_count_tampering_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    object.__setattr__(
        snapshot,
        "active_predictions",
        snapshot.active_predictions + 1,
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    assert result.validation_valid is False

    assert (
        result.checks[
            "latest_report_bindings_valid"
        ]
        is False
    )


def test_report_store_tampering_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, record, _ = (
        validate_snapshot(
            tmp_path
        )
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

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=VALIDATED_AT,
        )
    )

    assert result.validation_valid is False

    assert (
        result.checks[
            "source_audit_bindings_valid"
        ]
        is False
    )


def test_validation_before_generation_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=(
                snapshot.generated_at
                - timedelta(
                    seconds=1
                )
            ),
        )
    )

    assert result.validation_valid is False

    assert (
        result.checks[
            "timestamp_order_valid"
        ]
        is False
    )


def test_naive_validated_at_rejected(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=store,
            validated_at=(
                VALIDATED_AT.replace(
                    tzinfo=None
                )
            ),
        )


def test_invalid_snapshot_type_rejected(
    tmp_path,
) -> None:
    _, _, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    with pytest.raises(
        TypeError,
        match="snapshot",
    ):
        validate_noc_wall_dashboard_snapshot(
            snapshot="invalid",
            report_store=store,
            validated_at=VALIDATED_AT,
        )


def test_invalid_report_store_type_rejected(
    tmp_path,
) -> None:
    _, snapshot, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    with pytest.raises(
        TypeError,
        match="report_store",
    ):
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store="invalid",
            validated_at=VALIDATED_AT,
        )


def test_validation_without_report_store_warns(
    tmp_path,
) -> None:
    _, snapshot, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    result = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=None,
            validated_at=VALIDATED_AT,
        )
    )

    assert result.validation_warnings

    assert any(
        "Report store was not supplied"
        in warning
        for warning
        in result.validation_warnings
    )


def test_validator_class_interface(
    tmp_path,
) -> None:
    _, snapshot, store, *_ = (
        validate_snapshot(
            tmp_path
        )
    )

    validator = NOCWallDashboardValidator()

    result = validator.validate(
        snapshot=snapshot,
        report_store=store,
        validated_at=VALIDATED_AT,
    )

    assert result.validation_valid is True


def test_all_required_checks_present(
    tmp_path,
) -> None:
    result, *_ = validate_snapshot(
        tmp_path
    )

    assert set(
        NOCWallDashboardValidator
        .REQUIRED_CHECKS
    ) == set(
        result.checks
    )
