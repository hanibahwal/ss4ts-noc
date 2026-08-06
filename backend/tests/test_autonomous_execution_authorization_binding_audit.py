from __future__ import annotations

from datetime import datetime
import json
import sqlite3

import pytest

from app.services.autonomous_execution_authorization_binding_audit import (
    AutonomousExecutionAuthorizationBindingAuditVerifier,
    verify_autonomous_execution_authorization_binding_store,
)
from app.services.autonomous_execution_authorization_binding_store import (
    AutonomousExecutionAuthorizationBindingStore,
)
from tests.test_autonomous_execution_authorization_binding_service import (
    NOW,
)
from tests.test_autonomous_execution_authorization_binding_store import (
    make_binding,
)


def make_store_with_records(
    tmp_path,
    *,
    count: int = 2,
):
    store = AutonomousExecutionAuthorizationBindingStore(
        tmp_path / "bindings.db"
    )

    for index in range(count):
        suffix = f"audit-{index + 1}"

        store.append(
            binding=make_binding(
                tmp_path / suffix,
                suffix=suffix,
            ),
            stored_at=NOW,
        )

    return store


def test_valid_store_audit(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path
    )

    audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    assert audit.audit_valid is True
    assert audit.record_count == 2
    assert audit.verified_record_count == 2

    assert audit.first_sequence_number == 1
    assert audit.last_sequence_number == 2

    assert audit.first_record_hash
    assert audit.last_record_hash

    assert audit.record_hashes_valid is True
    assert audit.hash_chain_valid is True
    assert audit.sequence_integrity_valid is True
    assert audit.binding_fingerprints_valid is True
    assert audit.binding_payloads_valid is True
    assert audit.intent_bindings_valid is True
    assert audit.authorization_bindings_valid is True
    assert audit.duplicate_identities_valid is True
    assert audit.safety_claims_valid is True

    assert audit.errors == ()


def test_audit_report_is_never_executable(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=1,
    )

    audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    payload = audit.to_dict()

    assert audit.execution_authorization_created is False
    assert audit.authorization_approved is False
    assert audit.execution_allowed is False
    assert audit.can_execute is False

    assert payload["can_execute"] is False
    assert payload["safety"]["audit_only"] is True
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["database_mutated"] is False


def test_empty_store_is_valid_with_warning(
    tmp_path,
) -> None:
    store = AutonomousExecutionAuthorizationBindingStore(
        tmp_path / "empty.db"
    )

    audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    assert audit.audit_valid is True
    assert audit.record_count == 0
    assert audit.verified_record_count == 0
    assert audit.warnings


def test_tampered_record_hash_fails_audit(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=1,
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            """
            UPDATE
                autonomous_execution_authorization_binding_records
            SET
                record_hash = ?
            WHERE
                sequence_number = 1
            """,
            (
                "f" * 64,
            ),
        )
        connection.commit()

    audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    assert audit.audit_valid is False
    assert audit.record_hashes_valid is False
    assert audit.hash_chain_valid is False
    assert audit.errors


def test_tampered_previous_hash_fails_audit(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=2,
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        connection.execute(
            """
            UPDATE
                autonomous_execution_authorization_binding_records
            SET
                previous_record_hash = ?
            WHERE
                sequence_number = 2
            """,
            (
                "e" * 64,
            ),
        )
        connection.commit()

    audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    assert audit.audit_valid is False
    assert audit.hash_chain_valid is False


def test_tampered_binding_payload_fails_audit(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=1,
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        row = connection.execute(
            """
            SELECT binding_payload
            FROM
                autonomous_execution_authorization_binding_records
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["plan_id"] = "tampered-plan"

        connection.execute(
            """
            UPDATE
                autonomous_execution_authorization_binding_records
            SET
                binding_payload = ?
            WHERE
                sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    assert audit.audit_valid is False
    assert audit.binding_payloads_valid is False
    assert audit.binding_fingerprints_valid is False


def test_unsafe_claim_fails_audit(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=1,
    )

    with sqlite3.connect(
        store.database_path
    ) as connection:
        row = connection.execute(
            """
            SELECT binding_payload
            FROM
                autonomous_execution_authorization_binding_records
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["can_execute"] = True

        connection.execute(
            """
            UPDATE
                autonomous_execution_authorization_binding_records
            SET
                binding_payload = ?
            WHERE
                sequence_number = 1
            """,
            (
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.commit()

    audit = (
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=NOW,
        )
    )

    assert audit.audit_valid is False
    assert audit.safety_claims_valid is False


def test_audit_does_not_mutate_store(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=1,
    )

    before = store.count()

    verify_autonomous_execution_authorization_binding_store(
        store,
        audited_at=NOW,
    )

    after = store.count()

    assert before == after == 1


def test_invalid_store_type_rejected(
) -> None:
    with pytest.raises(
        TypeError,
        match=(
            "AutonomousExecutionAuthorization"
            "BindingStore"
        ),
    ):
        verify_autonomous_execution_authorization_binding_store(
            "invalid"
        )


def test_naive_audited_at_rejected(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=1,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        verify_autonomous_execution_authorization_binding_store(
            store,
            audited_at=datetime(
                2026,
                8,
                6,
                22,
                15,
            ),
        )


def test_verifier_direct_entrypoint(
    tmp_path,
) -> None:
    store = make_store_with_records(
        tmp_path,
        count=1,
    )

    audit = (
        AutonomousExecutionAuthorizationBindingAuditVerifier(
            store.database_path
        ).verify(
            audited_at=NOW
        )
    )

    assert audit.audit_valid is True
    assert audit.record_count == 1
