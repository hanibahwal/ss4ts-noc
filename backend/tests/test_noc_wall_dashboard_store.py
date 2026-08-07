from __future__ import annotations

from datetime import timedelta
import sqlite3

import pytest

from app.services.noc_wall_dashboard_store import (
    GENESIS_RECORD_HASH,
    NOCWallDashboardDuplicateError,
    NOCWallDashboardIntegrityError,
    NOCWallDashboardRecord,
    NOCWallDashboardStore,
)
from app.services.noc_wall_dashboard_validation import (
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

STORED_AT = (
    VALIDATED_AT
    + timedelta(
        minutes=5
    )
)


def append_snapshot(
    tmp_path,
    *,
    dashboard_store=None,
):
    snapshot, report_store, *_ = (
        build_snapshot(
            tmp_path
            / "source"
        )
    )

    validation = (
        validate_noc_wall_dashboard_snapshot(
            snapshot=snapshot,
            report_store=report_store,
            validated_at=VALIDATED_AT,
        )
    )

    store = (
        dashboard_store
        or NOCWallDashboardStore(
            tmp_path
            / "dashboard.db"
        )
    )

    record = store.append(
        snapshot=snapshot,
        validation=validation,
        stored_at=STORED_AT,
    )

    return (
        record,
        store,
        snapshot,
        validation,
        report_store,
    )


def test_append_snapshot(
    tmp_path,
) -> None:
    record, store, snapshot, validation, _ = (
        append_snapshot(
            tmp_path
        )
    )

    assert isinstance(
        record,
        NOCWallDashboardRecord,
    )

    assert record.sequence_number == 1

    assert record.dashboard_id == (
        snapshot.dashboard_id
    )

    assert record.validation_id == (
        validation.validation_id
    )

    assert record.previous_record_hash == (
        GENESIS_RECORD_HASH
    )

    assert record.verify_hash() is True
    assert store.count() == 1


def test_get_snapshot(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    loaded = store.get(
        record.dashboard_id
    )

    assert loaded == record


def test_get_by_fingerprint(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    loaded = store.get_by_fingerprint(
        record.dashboard_fingerprint
    )

    assert loaded == record


def test_missing_snapshot_returns_none(
    tmp_path,
) -> None:
    store = NOCWallDashboardStore(
        tmp_path
        / "dashboard.db"
    )

    assert (
        store.get(
            "noc-wall-dashboard:missing"
        )
        is None
    )


def test_duplicate_snapshot_rejected(
    tmp_path,
) -> None:
    (
        _,
        store,
        snapshot,
        validation,
        _,
    ) = append_snapshot(
        tmp_path
    )

    with pytest.raises(
        NOCWallDashboardDuplicateError,
    ):
        store.append(
            snapshot=snapshot,
            validation=validation,
            stored_at=(
                STORED_AT
                + timedelta(
                    minutes=1
                )
            ),
        )


def test_invalid_validation_binding_rejected(
    tmp_path,
) -> None:
    (
        _,
        _,
        snapshot,
        validation,
        _,
    ) = append_snapshot(
        tmp_path
    )

    object.__setattr__(
        validation,
        "dashboard_id",
        "noc-wall-dashboard:tampered",
    )

    store = NOCWallDashboardStore(
        tmp_path
        / "second.db"
    )

    with pytest.raises(
        NOCWallDashboardIntegrityError,
    ):
        store.append(
            snapshot=snapshot,
            validation=validation,
            stored_at=STORED_AT,
        )


def test_rejected_validation_cannot_be_stored(
    tmp_path,
) -> None:
    (
        _,
        _,
        snapshot,
        validation,
        _,
    ) = append_snapshot(
        tmp_path
    )

    object.__setattr__(
        validation,
        "validation_valid",
        False,
    )

    object.__setattr__(
        validation,
        "dashboard_accepted",
        False,
    )

    store = NOCWallDashboardStore(
        tmp_path
        / "rejected.db"
    )

    with pytest.raises(
        NOCWallDashboardIntegrityError,
    ):
        store.append(
            snapshot=snapshot,
            validation=validation,
            stored_at=STORED_AT,
        )


def test_stored_at_before_validation_rejected(
    tmp_path,
) -> None:
    (
        _,
        _,
        snapshot,
        validation,
        _,
    ) = append_snapshot(
        tmp_path
    )

    store = NOCWallDashboardStore(
        tmp_path
        / "early.db"
    )

    with pytest.raises(
        ValueError,
        match="stored_at",
    ):
        store.append(
            snapshot=snapshot,
            validation=validation,
            stored_at=(
                validation.validated_at
                - timedelta(
                    seconds=1
                )
            ),
        )


def test_naive_stored_at_rejected(
    tmp_path,
) -> None:
    (
        _,
        _,
        snapshot,
        validation,
        _,
    ) = append_snapshot(
        tmp_path
    )

    store = NOCWallDashboardStore(
        tmp_path
        / "naive.db"
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        store.append(
            snapshot=snapshot,
            validation=validation,
            stored_at=(
                STORED_AT.replace(
                    tzinfo=None
                )
            ),
        )


def test_chain_is_valid(
    tmp_path,
) -> None:
    _, store, *_ = append_snapshot(
        tmp_path
    )

    assert store.verify_chain() is True


def test_record_hash_tampering_detected(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET overall_health_score = ?
            WHERE sequence_number = ?
            """,
            (
                1.0,
                record.sequence_number,
            ),
        )

        connection.commit()

    assert store.verify_chain() is False


def test_snapshot_payload_tampering_detected(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET snapshot_payload = ?
            WHERE sequence_number = ?
            """,
            (
                '{"dashboard_id":"tampered"}',
                record.sequence_number,
            ),
        )

        connection.commit()

    assert store.verify_chain() is False


def test_list_records(
    tmp_path,
) -> None:
    record, store, *_ = append_snapshot(
        tmp_path
    )

    records = store.list_records()

    assert records == (
        record,
    )


def test_invalid_limit_rejected(
    tmp_path,
) -> None:
    store = NOCWallDashboardStore(
        tmp_path
        / "dashboard.db"
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        store.list_records(
            limit=0
        )


def test_empty_store_chain_is_valid(
    tmp_path,
) -> None:
    store = NOCWallDashboardStore(
        tmp_path
        / "dashboard.db"
    )

    assert store.count() == 0
    assert store.verify_chain() is True


def test_record_never_grants_execution(
    tmp_path,
) -> None:
    record, *_ = append_snapshot(
        tmp_path
    )

    payload = record.to_dict()

    assert record.incident_created is False
    assert record.recommendation_executed is False
    assert record.decision_created is False
    assert record.authorization_created is False
    assert record.execution_allowed is False
    assert record.can_execute is False

    assert payload["can_execute"] is False

    assert (
        payload["safety"]["append_only"]
        is True
    )

    assert (
        payload["safety"][
            "device_command_executed"
        ]
        is False
    )
