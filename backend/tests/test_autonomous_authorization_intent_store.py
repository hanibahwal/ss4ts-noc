from __future__ import annotations

from dataclasses import replace
import json
import sqlite3

import pytest

from app.services.autonomous_authorization_intent_store import (
    GENESIS_RECORD_HASH,
    AutonomousAuthorizationIntentDuplicate,
    AutonomousAuthorizationIntentIntegrityError,
    AutonomousAuthorizationIntentStore,
)
from app.services.autonomous_controlled_authorization_bridge import (
    create_autonomous_authorization_intent,
)
from tests.test_autonomous_controlled_authorization_bridge import (
    NOW,
    make_verified_inputs,
)


def make_intent(
    tmp_path,
    *,
    suffix: str = "1",
):
    record, audit = make_verified_inputs(
        tmp_path
    )

    return create_autonomous_authorization_intent(
        request_record=record,
        request_audit=audit,
        authorization_intent_id=(
            "autonomous-authorization-intent:"
            f"{suffix}"
        ),
        created_at=NOW,
    )


def test_append_and_get_intent(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path,
    )

    stored = store.append(
        intent=intent
    )

    loaded = store.get(
        intent.authorization_intent_id
    )

    assert loaded == stored
    assert stored.sequence_number == 1

    assert (
        stored.previous_record_hash
        == GENESIS_RECORD_HASH
    )

    assert stored.verify_hash() is True
    assert stored.can_execute is False


def test_intent_bindings_are_preserved(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path
    )

    record = store.append(
        intent=intent
    )

    assert (
        record.authorization_intent_id
        == intent.authorization_intent_id
    )

    assert (
        record.bridge_fingerprint
        == intent.bridge_fingerprint
    )

    assert (
        record.authorization_request_id
        == intent.authorization_request_id
    )

    assert (
        record.request_record_hash
        == intent.request_record_hash
    )

    assert (
        record.request_audit_id
        == intent.request_audit_id
    )

    assert (
        record.authorization_candidate_id
        == intent.authorization_candidate_id
    )

    assert (
        record.proposal_id
        == intent.proposal_id
    )


def test_duplicate_intent_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path
    )

    store.append(
        intent=intent
    )

    with pytest.raises(
        AutonomousAuthorizationIntentDuplicate,
    ):
        store.append(
            intent=intent
        )


def test_chain_links_multiple_intents(
    tmp_path,
) -> None:
    from dataclasses import fields

    from app.models.autonomous_authorization_intent import (
        AutonomousAuthorizationIntent,
    )

    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    first = make_intent(
        tmp_path / "first",
        suffix="first",
    )

    first_record = store.append(
        intent=first
    )

    # Copy the original dataclass values directly so enum and
    # datetime types remain intact. Do not use to_dict(), because
    # it serializes risk_class and timestamps.
    second_values = {
        field.name: getattr(
            first,
            field.name,
        )
        for field in fields(
            AutonomousAuthorizationIntent
        )
        if field.name != "bridge_fingerprint"
    }

    second_values.update(
        {
            "authorization_intent_id":
                "autonomous-authorization-intent:second",
            "authorization_request_id":
                "autonomous-authorization-request:second",
            "request_record_hash":
                "2" * 64,
            "request_fingerprint":
                "3" * 64,
            "request_audit_id":
                "autonomous-request-audit:second",
            "authorization_candidate_id":
                "autonomous-authorization-candidate:second",
            "candidate_record_hash":
                "4" * 64,
            "candidate_fingerprint":
                "5" * 64,
            "proposal_id":
                "autonomous-operation-proposal:second",
            "proposal_record_hash":
                "6" * 64,
        }
    )

    provisional = (
        AutonomousAuthorizationIntent.__new__(
            AutonomousAuthorizationIntent
        )
    )

    for field_name, value in (
        second_values.items()
    ):
        object.__setattr__(
            provisional,
            field_name,
            value,
        )

    object.__setattr__(
        provisional,
        "bridge_fingerprint",
        "",
    )

    second = AutonomousAuthorizationIntent(
        **second_values,
        bridge_fingerprint=(
            provisional.calculate_fingerprint()
        ),
    )

    second_record = store.append(
        intent=second
    )

    assert first_record.sequence_number == 1
    assert second_record.sequence_number == 2

    assert (
        second_record.previous_record_hash
        == first_record.record_hash
    )

    assert store.verify_chain() is True

def test_count_list_and_request_lookup(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path
    )

    stored = store.append(
        intent=intent
    )

    assert store.count() == 1
    assert store.list_records() == [stored]

    assert (
        store.get_by_request_id(
            intent.authorization_request_id
        )
        == stored
    )


def test_empty_store_chain_is_valid(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    assert store.count() == 0
    assert store.verify_chain() is True


def test_invalid_intent_type_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    with pytest.raises(
        TypeError,
        match="AutonomousAuthorizationIntent",
    ):
        store.append(
            intent={},
        )


def test_tampered_bridge_fingerprint_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path
    )

    # The immutable model rejects a bad fingerprint during
    # reconstruction, before the store receives the object.
    with pytest.raises(
        ValueError,
        match="bridge_fingerprint",
    ):
        replace(
            intent,
            bridge_fingerprint="f" * 64,
        )

    assert store.count() == 0


def test_tampered_payload_detected(
    tmp_path,
) -> None:
    database = tmp_path / "intents.db"

    store = AutonomousAuthorizationIntentStore(
        database
    )

    intent = make_intent(
        tmp_path
    )

    store.append(
        intent=intent
    )

    with sqlite3.connect(
        database
    ) as connection:
        payload = json.loads(
            connection.execute(
                """
                SELECT intent_payload
                FROM autonomous_authorization_intent_records
                """
            ).fetchone()[0]
        )

        payload["can_execute"] = True

        connection.execute(
            """
            UPDATE autonomous_authorization_intent_records
            SET intent_payload = ?
            """,
            (
                json.dumps(
                    payload,
                    sort_keys=True,
                ),
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousAuthorizationIntentIntegrityError,
    ):
        store.list_records()


def test_broken_previous_hash_detected(
    tmp_path,
) -> None:
    database = tmp_path / "intents.db"

    store = AutonomousAuthorizationIntentStore(
        database
    )

    intent = make_intent(
        tmp_path
    )

    store.append(
        intent=intent
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE autonomous_authorization_intent_records
            SET previous_record_hash = ?
            """,
            (
                "f" * 64,
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousAuthorizationIntentIntegrityError,
    ):
        store.verify_chain()


def test_record_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationIntentStore(
        tmp_path / "intents.db"
    )

    intent = make_intent(
        tmp_path
    )

    payload = store.append(
        intent=intent
    ).to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "immutable_record": True,
        "append_only": True,
        "authorization_intent_only": True,
        "execution_authorization_created": False,
        "execution_authorization_stored": False,
        "authorization_approved": False,
        "authorization_token_created": False,
        "approval_claim_created": False,
        "execution_lease_created": False,
        "execution_allowed": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_access_performed": False,
        "command_generated": False,
        "device_command_executed": False,
    }
