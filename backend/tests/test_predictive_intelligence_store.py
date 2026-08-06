from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from app.services.predictive_intelligence_store import (
    GENESIS_RECORD_HASH,
    PredictiveIntelligenceDuplicate,
    PredictiveIntelligenceIntegrityError,
    PredictiveIntelligenceRecord,
    PredictiveIntelligenceStore,
)
from app.services.predictive_intelligence_validation import (
    validate_predictive_intelligence,
)
from tests.test_predictive_intelligence import (
    NOW,
    make_prediction,
)


STORED_AT = (
    NOW
    + timedelta(
        minutes=3
    )
)


def make_validated_prediction(
    *,
    suffix: str = "one",
):
    prediction = make_prediction(
        prediction_id=(
            "predictive-intelligence:"
            f"{suffix}"
        ),
        subject_id=(
            "link:buqayq-uqair:"
            f"{suffix}"
        ),
        metadata={
            "suffix": suffix,
        },
    )

    validation = (
        validate_predictive_intelligence(
            prediction,
            validated_at=(
                NOW
                + timedelta(
                    minutes=2
                )
            ),
        )
    )

    assert validation.validation_valid is True

    return prediction, validation


def append_prediction(
    store: PredictiveIntelligenceStore,
    *,
    suffix: str = "one",
):
    prediction, validation = (
        make_validated_prediction(
            suffix=suffix
        )
    )

    return store.append(
        prediction=prediction,
        validation=validation,
        stored_at=STORED_AT,
    )


def test_append_predictive_intelligence(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    record = append_prediction(
        store
    )

    assert isinstance(
        record,
        PredictiveIntelligenceRecord,
    )

    assert record.sequence_number == 1
    assert (
        record.previous_record_hash
        == GENESIS_RECORD_HASH
    )

    assert record.validation_valid is True
    assert record.verify_hash() is True
    assert record.can_execute is False
    assert store.count() == 1
    assert store.verify_chain() is True


def test_get_prediction_by_id(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    created = append_prediction(
        store
    )

    loaded = store.get(
        created.prediction_id
    )

    assert loaded is not None
    assert (
        loaded.prediction_id
        == created.prediction_id
    )

    assert (
        loaded.prediction_fingerprint
        == created.prediction_fingerprint
    )


def test_get_prediction_by_fingerprint(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    created = append_prediction(
        store
    )

    loaded = store.get_by_fingerprint(
        created.prediction_fingerprint
    )

    assert loaded is not None
    assert (
        loaded.prediction_id
        == created.prediction_id
    )


def test_duplicate_prediction_rejected(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    prediction, validation = (
        make_validated_prediction()
    )

    store.append(
        prediction=prediction,
        validation=validation,
        stored_at=STORED_AT,
    )

    with pytest.raises(
        PredictiveIntelligenceDuplicate,
    ):
        store.append(
            prediction=prediction,
            validation=validation,
            stored_at=STORED_AT,
        )


def test_two_records_form_hash_chain(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    first = append_prediction(
        store,
        suffix="first",
    )

    second = append_prediction(
        store,
        suffix="second",
    )

    assert first.sequence_number == 1
    assert second.sequence_number == 2

    assert (
        second.previous_record_hash
        == first.record_hash
    )

    assert store.verify_chain() is True


def test_list_records(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    append_prediction(
        store,
        suffix="first",
    )

    append_prediction(
        store,
        suffix="second",
    )

    records = store.list_records()

    assert len(records) == 2

    assert [
        record.sequence_number
        for record in records
    ] == [
        1,
        2,
    ]


def test_invalid_validation_rejected(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    prediction = make_prediction(
        probability_percent=20,
        confidence_percent=20,
    )

    validation = (
        validate_predictive_intelligence(
            prediction,
            validated_at=(
                NOW
                + timedelta(
                    minutes=2
                )
            ),
        )
    )

    assert validation.validation_valid is False

    with pytest.raises(
        PredictiveIntelligenceIntegrityError,
        match="validation",
    ):
        store.append(
            prediction=prediction,
            validation=validation,
            stored_at=STORED_AT,
        )


def test_mismatched_validation_rejected(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    first, _ = (
        make_validated_prediction(
            suffix="first"
        )
    )

    _, second_validation = (
        make_validated_prediction(
            suffix="second"
        )
    )

    with pytest.raises(
        PredictiveIntelligenceIntegrityError,
        match="prediction_id",
    ):
        store.append(
            prediction=first,
            validation=second_validation,
            stored_at=STORED_AT,
        )


def test_tampered_fingerprint_rejected(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    prediction, validation = (
        make_validated_prediction()
    )

    object.__setattr__(
        prediction,
        "prediction_fingerprint",
        "f" * 64,
    )

    with pytest.raises(
        PredictiveIntelligenceIntegrityError,
        match="fingerprint",
    ):
        store.append(
            prediction=prediction,
            validation=validation,
            stored_at=STORED_AT,
        )


def test_stored_at_before_created_at_rejected(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    prediction, validation = (
        make_validated_prediction()
    )

    with pytest.raises(
        PredictiveIntelligenceIntegrityError,
        match="stored_at",
    ):
        store.append(
            prediction=prediction,
            validation=validation,
            stored_at=(
                prediction.created_at
                - timedelta(
                    seconds=1
                )
            ),
        )


def test_tampered_database_record_breaks_chain(
    tmp_path,
) -> None:
    database = (
        tmp_path
        / "predictive.db"
    )

    store = PredictiveIntelligenceStore(
        database
    )

    append_prediction(
        store
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET subject_id = ?
            WHERE sequence_number = 1
            """,
            (
                "link:tampered",
            ),
        )

        connection.commit()

    assert store.verify_chain() is False


def test_record_payload_never_grants_execution(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    record = append_prediction(
        store
    )

    payload = record.to_dict()

    assert record.incident_created is False
    assert record.recommendation_created is False
    assert record.decision_created is False
    assert record.authorization_created is False
    assert record.approval_claim_created is False
    assert record.execution_lease_created is False
    assert record.execution_allowed is False
    assert record.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"][
            "immutable_predictive_store"
        ]
        is True
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )


def test_missing_prediction_returns_none(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    assert (
        store.get(
            "predictive-intelligence:missing"
        )
        is None
    )


def test_invalid_list_arguments_rejected(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        store.list_records(
            limit=0
        )

    with pytest.raises(
        ValueError,
        match="offset",
    ):
        store.list_records(
            offset=-1
        )


def test_naive_stored_at_rejected(
    tmp_path,
) -> None:
    store = PredictiveIntelligenceStore(
        tmp_path
        / "predictive.db"
    )

    prediction, validation = (
        make_validated_prediction()
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        store.append(
            prediction=prediction,
            validation=validation,
            stored_at=STORED_AT.replace(
                tzinfo=None
            ),
        )
