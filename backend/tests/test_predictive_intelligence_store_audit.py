from __future__ import annotations

from datetime import datetime, timedelta
import json
import sqlite3

import pytest

from app.services.predictive_intelligence_store import (
    PredictiveIntelligenceStore,
)
from app.services.predictive_intelligence_store_audit import (
    PredictiveIntelligenceStoreAuditReport,
    PredictiveIntelligenceStoreAuditVerifier,
    verify_predictive_intelligence_store,
)
from tests.test_predictive_intelligence import (
    NOW,
)
from tests.test_predictive_intelligence_store import (
    append_prediction,
)


AUDITED_AT = (
    NOW
    + timedelta(
        minutes=5
    )
)


def make_store(
    tmp_path,
    *,
    count: int = 1,
):
    database = (
        tmp_path
        / "predictive-audit.db"
    )

    store = PredictiveIntelligenceStore(
        database
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

    return store, database


def audit_store(
    store,
):
    return verify_predictive_intelligence_store(
        store,
        audited_at=AUDITED_AT,
    )


def test_valid_predictive_store_audit(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path,
        count=2,
    )

    report = audit_store(
        store
    )

    assert isinstance(
        report,
        PredictiveIntelligenceStoreAuditReport,
    )

    assert report.record_count == 2
    assert report.first_sequence_number == 1
    assert report.last_sequence_number == 2

    assert report.record_hashes_valid is True
    assert report.hash_chain_valid is True
    assert report.sequence_integrity_valid is True
    assert (
        report.prediction_fingerprints_valid
        is True
    )
    assert report.prediction_payloads_valid is True
    assert report.validation_payloads_valid is True
    assert report.duplicate_identities_valid is True
    assert report.timestamp_consistency_valid is True
    assert report.safety_claims_valid is True

    assert report.issues == ()
    assert report.audit_valid is True
    assert report.can_execute is False


def test_empty_store_is_valid(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path,
        count=0,
    )

    report = audit_store(
        store
    )

    assert report.record_count == 0
    assert report.first_sequence_number is None
    assert report.last_sequence_number is None
    assert report.audit_valid is True


def test_audit_does_not_modify_store(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path,
        count=2,
    )

    before_count = store.count()

    report = audit_store(
        store
    )

    assert report.audit_valid is True
    assert store.count() == before_count


def test_report_never_grants_execution(
    tmp_path,
) -> None:
    store, _ = make_store(
        tmp_path
    )

    report = audit_store(
        store
    )

    payload = report.to_dict()

    assert report.incident_created is False
    assert report.recommendation_created is False
    assert report.decision_created is False
    assert report.authorization_created is False
    assert report.approval_claim_created is False
    assert report.execution_lease_created is False
    assert report.execution_allowed is False
    assert report.can_execute is False

    assert payload["can_execute"] is False
    assert (
        payload["safety"][
            "predictive_store_audit_only"
        ]
        is True
    )
    assert (
        payload["safety"][
            "store_mutated"
        ]
        is False
    )


def test_tampered_record_hash_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET record_hash = ?
            WHERE sequence_number = 1
            """,
            (
                "f" * 64,
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_broken_hash_chain_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path,
        count=2,
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET previous_record_hash = ?
            WHERE sequence_number = 2
            """,
            (
                "a" * 64,
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.hash_chain_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_prediction_payload_tampering_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT prediction_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["subject_id"] = (
            "link:tampered"
        )

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET prediction_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.prediction_payloads_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_prediction_fingerprint_tampering_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET predicted_value = ?
            WHERE sequence_number = 1
            """,
            (
                -95.0,
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert (
        report.prediction_fingerprints_valid
        is False
    )
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_validation_payload_tampering_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT validation_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["validation_valid"] = False
        payload["prediction_accepted"] = False

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET validation_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.validation_payloads_valid is False
    assert report.record_hashes_valid is False
    assert report.audit_valid is False


def test_invalid_timestamp_order_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET stored_at = ?
            WHERE sequence_number = 1
            """,
            (
                "2020-01-01T00:00:00+00:00",
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert (
        report.timestamp_consistency_valid
        is False
    )
    assert report.audit_valid is False


def test_unsafe_prediction_claim_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT prediction_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["decision_created"] = True
        payload["can_execute"] = True

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET prediction_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.safety_claims_valid is False
    assert report.audit_valid is False


def test_unsafe_validation_claim_detected(
    tmp_path,
) -> None:
    store, database = make_store(
        tmp_path
    )

    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT validation_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["authorization_created"] = True

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET validation_payload = ?
            WHERE sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    report = audit_store(
        store
    )

    assert report.safety_claims_valid is False
    assert report.audit_valid is False


def test_invalid_inputs_rejected(
    tmp_path,
) -> None:
    verifier = (
        PredictiveIntelligenceStoreAuditVerifier()
    )

    with pytest.raises(
        TypeError,
        match="store",
    ):
        verifier.verify(
            store="invalid",
            audited_at=AUDITED_AT,
        )

    store, _ = make_store(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        verifier.verify(
            store=store,
            audited_at=datetime(
                2026,
                8,
                6,
                23,
                0,
            ),
        )
