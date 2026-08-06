from __future__ import annotations

from datetime import datetime
import sqlite3

import pytest

from app.models.autonomous_execution_authorization_binding import (
    AutonomousExecutionAuthorizationBinding,
)
from app.services.autonomous_execution_authorization_binding import (
    validate_execution_authorization_binding,
)
from app.services.autonomous_execution_authorization_binding_store import (
    AutonomousExecutionAuthorizationBindingDuplicate,
    AutonomousExecutionAuthorizationBindingStore,
)
from tests.test_autonomous_execution_authorization_binding_service import (
    NOW,
    make_verified_inputs,
)


def make_binding(
    tmp_path,
    *,
    suffix: str = "one",
):
    record, audit, authorization = (
        make_verified_inputs(
            tmp_path
        )
    )

    authorization.authorization_id = (
        f"authorization:h25-store:{suffix}"
    )

    binding = validate_execution_authorization_binding(
        intent_record=record,
        intent_audit=audit,
        execution_authorization=authorization,
        binding_id=(
            "autonomous-execution-authorization-"
            f"binding:{suffix}"
        ),
        created_at=NOW,
    )

    if suffix == "one":
        return binding

    values = {
        "binding_id":
            binding.binding_id,
        "authorization_intent_id":
            f"{binding.authorization_intent_id}:{suffix}",
        "intent_record_hash":
            __import__(
                "hashlib"
            ).sha256(
                (
                    binding.intent_record_hash
                    + ":"
                    + suffix
                ).encode("utf-8")
            ).hexdigest(),
        "intent_bridge_fingerprint":
            __import__(
                "hashlib"
            ).sha256(
                (
                    binding.intent_bridge_fingerprint
                    + ":"
                    + suffix
                ).encode("utf-8")
            ).hexdigest(),
        "intent_audit_id":
            f"{binding.intent_audit_id}:{suffix}",
        "intent_audit_valid":
            binding.intent_audit_valid,
        "execution_authorization_id":
            binding.execution_authorization_id,
        "plan_id":
            binding.plan_id,
        "decision_id":
            binding.decision_id,
        "risk_class":
            binding.risk_class,
        "authorization_status":
            binding.authorization_status,
        "authorization_decision":
            binding.authorization_decision,
        "created_at":
            binding.created_at,
        "expires_at":
            binding.expires_at,
    }

    provisional = (
        AutonomousExecutionAuthorizationBinding.__new__(
            AutonomousExecutionAuthorizationBinding
        )
    )

    for field, value in values.items():
        object.__setattr__(
            provisional,
            field,
            value,
        )

    object.__setattr__(
        provisional,
        "binding_fingerprint",
        "",
    )

    fingerprint = (
        provisional.calculate_fingerprint()
    )

    return AutonomousExecutionAuthorizationBinding(
        **values,
        binding_fingerprint=fingerprint,
    )


def test_append_binding(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    record = store.append(
        binding=make_binding(
            tmp_path
        ),
        stored_at=NOW,
    )

    assert record.sequence_number == 1
    assert record.verify_hash() is True
    assert record.can_execute is False
    assert store.count() == 1
    assert store.verify_chain() is True


def test_get_by_binding_id(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    stored = store.append(
        binding=make_binding(
            tmp_path
        ),
        stored_at=NOW,
    )

    loaded = store.get_by_binding_id(
        stored.binding_id
    )

    assert loaded == stored


def test_get_by_intent_id(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    stored = store.append(
        binding=make_binding(
            tmp_path
        ),
        stored_at=NOW,
    )

    loaded = (
        store.get_by_authorization_intent_id(
            stored.authorization_intent_id
        )
    )

    assert loaded == stored


def test_get_by_execution_authorization_id(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    stored = store.append(
        binding=make_binding(
            tmp_path
        ),
        stored_at=NOW,
    )

    loaded = (
        store.get_by_execution_authorization_id(
            stored.execution_authorization_id
        )
    )

    assert loaded == stored


def test_duplicate_binding_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    binding = make_binding(
        tmp_path
    )

    store.append(
        binding=binding,
        stored_at=NOW,
    )

    with pytest.raises(
        AutonomousExecutionAuthorizationBindingDuplicate,
    ):
        store.append(
            binding=binding,
            stored_at=NOW,
        )


def test_records_are_append_only(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    first = store.append(
        binding=make_binding(
            tmp_path / "first",
            suffix="first",
        ),
        stored_at=NOW,
    )

    second = store.append(
        binding=make_binding(
            tmp_path / "second",
            suffix="second",
        ),
        stored_at=NOW,
    )

    assert first.sequence_number == 1
    assert second.sequence_number == 2

    assert (
        second.previous_record_hash
        == first.record_hash
    )

    assert store.verify_chain() is True


def test_record_is_never_executable(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    record = store.append(
        binding=make_binding(
            tmp_path
        ),
        stored_at=NOW,
    )

    payload = record.to_dict()

    assert (
        record.execution_authorization_created
        is True
    )
    assert record.authorization_approved is False
    assert record.execution_allowed is False
    assert record.can_execute is False

    assert (
        payload["safety"]["immutable_record"]
        is True
    )
    assert (
        payload["safety"]["append_only"]
        is True
    )
    assert (
        payload["safety"]["authorization_approved"]
        is False
    )
    assert (
        payload["safety"]["execution_allowed"]
        is False
    )


def test_tampered_record_hash_breaks_chain(
    tmp_path,
) -> None:
    database = tmp_path / "bindings.db"

    store = (
        AutonomousExecutionAuthorizationBindingStore(
            database
        )
    )

    store.append(
        binding=make_binding(
            tmp_path
        ),
        stored_at=NOW,
    )

    with sqlite3.connect(
        database
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

    assert store.verify_chain() is False


def test_tampered_binding_payload_breaks_chain(
    tmp_path,
) -> None:
    database = tmp_path / "bindings.db"

    store = (
        AutonomousExecutionAuthorizationBindingStore(
            database
        )
    )

    store.append(
        binding=make_binding(
            tmp_path
        ),
        stored_at=NOW,
    )

    with sqlite3.connect(
        database
    ) as connection:
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
                '{"can_execute":true}',
            ),
        )
        connection.commit()

    assert store.verify_chain() is False


def test_naive_stored_at_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        store.append(
            binding=make_binding(
                tmp_path
            ),
            stored_at=datetime(
                2026,
                8,
                6,
                22,
                30,
            ),
        )


def test_invalid_binding_type_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    with pytest.raises(
        TypeError,
        match="binding",
    ):
        store.append(
            binding="invalid",
            stored_at=NOW,
        )


def test_missing_records_return_none(
    tmp_path,
) -> None:
    store = (
        AutonomousExecutionAuthorizationBindingStore(
            tmp_path / "bindings.db"
        )
    )

    assert store.get(999) is None

    assert (
        store.get_by_binding_id(
            "missing"
        )
        is None
    )

    assert (
        store.get_by_authorization_intent_id(
            "missing"
        )
        is None
    )

    assert (
        store.get_by_execution_authorization_id(
            "missing"
        )
        is None
    )
