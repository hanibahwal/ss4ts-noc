from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sqlite3

import pytest

from app.services.autonomous_authorization_candidate_audit import (
    verify_autonomous_authorization_candidate_store,
)
from app.services.autonomous_authorization_candidate_store import (
    AutonomousAuthorizationCandidateStore,
)
from app.services.autonomous_authorization_request import (
    create_autonomous_authorization_request,
)
from app.services.autonomous_authorization_request_store import (
    GENESIS_RECORD_HASH,
    AutonomousAuthorizationRequestDuplicate,
    AutonomousAuthorizationRequestIntegrityError,
    AutonomousAuthorizationRequestStore,
)
from tests.test_autonomous_authorization_candidate_store import (
    make_candidate,
)


NOW = datetime(
    2026,
    8,
    6,
    20,
    30,
    tzinfo=timezone.utc,
)


def make_request(
    tmp_path,
    *,
    number: int = 1,
):
    candidate_store = (
        AutonomousAuthorizationCandidateStore(
            tmp_path
            / f"candidates-{number}.db"
        )
    )

    candidate_record = candidate_store.append(
        candidate=make_candidate(
            tmp_path,
            number=number,
        )
    )

    candidate_audit = (
        verify_autonomous_authorization_candidate_store(
            candidate_store
        )
    )

    return create_autonomous_authorization_request(
        candidate_record=candidate_record,
        candidate_audit=candidate_audit,
        requester_id=(
            f"engineer:hani:{number}"
        ),
        request_reason=(
            "Controlled authorization review "
            f"request {number}"
        ),
        risk_class="high",
        dry_run_required=True,
        rollback_required=True,
        verification_required=True,
        requested_at=NOW,
        authorization_request_id=(
            "autonomous-authorization-request:"
            f"store-{number}"
        ),
    )


def test_append_and_get_request(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    request = make_request(
        tmp_path
    )

    record = store.append(
        request=request
    )

    loaded = store.get(
        request.authorization_request_id
    )

    assert loaded == record
    assert record.sequence_number == 1

    assert (
        record.previous_record_hash
        == GENESIS_RECORD_HASH
    )

    assert record.verify_hash() is True
    assert record.can_execute is False
    assert record.execution_allowed is False


def test_request_bindings_are_preserved(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    request = make_request(
        tmp_path
    )

    record = store.append(
        request=request
    )

    assert (
        record.authorization_request_id
        == request.authorization_request_id
    )

    assert (
        record.request_fingerprint
        == request.request_fingerprint
    )

    assert (
        record.authorization_candidate_id
        == request.authorization_candidate_id
    )

    assert (
        record.candidate_record_hash
        == request.candidate_record_hash
    )

    assert (
        record.proposal_id
        == request.proposal_id
    )


def test_duplicate_request_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    request = make_request(
        tmp_path
    )

    store.append(
        request=request
    )

    with pytest.raises(
        AutonomousAuthorizationRequestDuplicate,
    ):
        store.append(
            request=request
        )


def test_chain_links_multiple_requests(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    first = store.append(
        request=make_request(
            tmp_path,
            number=1,
        )
    )

    second = store.append(
        request=make_request(
            tmp_path,
            number=2,
        )
    )

    assert first.sequence_number == 1
    assert second.sequence_number == 2

    assert (
        second.previous_record_hash
        == first.record_hash
    )

    assert store.verify_chain() is True


def test_count_list_and_candidate_lookup(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    requests = [
        make_request(
            tmp_path,
            number=number,
        )
        for number in range(
            1,
            4,
        )
    ]

    for request in requests:
        store.append(
            request=request
        )

    records = store.list_records()

    assert store.count() == 3

    assert [
        record.sequence_number
        for record in records
    ] == [
        1,
        2,
        3,
    ]

    loaded = store.get_by_candidate_id(
        requests[1]
        .authorization_candidate_id
    )

    assert loaded is not None

    assert (
        loaded.authorization_request_id
        == requests[1]
        .authorization_request_id
    )


def test_empty_store_chain_is_valid(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    assert store.count() == 0
    assert store.verify_chain() is True


def test_invalid_request_type_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    with pytest.raises(
        TypeError,
        match=(
            "AutonomousControlledAuthorizationRequest"
        ),
    ):
        store.append(
            request="invalid"
        )


def test_tampered_request_fingerprint_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    request = make_request(
        tmp_path
    )

    tampered = replace(
        request
    )

    object.__setattr__(
        tampered,
        "request_fingerprint",
        "f" * 64,
    )

    with pytest.raises(
        AutonomousAuthorizationRequestIntegrityError,
        match="fingerprint mismatch",
    ):
        store.append(
            request=tampered
        )


def test_tampered_payload_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    request = make_request(
        tmp_path
    )

    store.append(
        request=request
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE
                autonomous_authorization_request_records
            SET request_payload = ?
            WHERE sequence_number = 1
            """,
            (
                '{"tampered":true}',
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousAuthorizationRequestIntegrityError,
        match="hash mismatch",
    ):
        store.get(
            request.authorization_request_id
        )


def test_broken_previous_hash_detected(
    tmp_path,
) -> None:
    database = tmp_path / "requests.db"

    store = AutonomousAuthorizationRequestStore(
        database
    )

    store.append(
        request=make_request(
            tmp_path,
            number=1,
        )
    )

    store.append(
        request=make_request(
            tmp_path,
            number=2,
        )
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE
                autonomous_authorization_request_records
            SET previous_record_hash = ?
            WHERE sequence_number = 2
            """,
            (
                "a" * 64,
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousAuthorizationRequestIntegrityError,
    ):
        store.verify_chain()


def test_record_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationRequestStore(
        tmp_path / "requests.db"
    )

    record = store.append(
        request=make_request(
            tmp_path
        )
    )

    payload = record.to_dict()

    assert payload["can_execute"] is False
    assert payload["execution_allowed"] is False
    assert payload["authorization_created"] is False

    assert payload["safety"] == {
        "immutable_record": True,
        "append_only": True,
        "controlled_authorization_request_only": True,
        "execution_authorization_created": False,
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
