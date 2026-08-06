from __future__ import annotations

from dataclasses import replace
import sqlite3

import pytest

from app.services.autonomous_authorization_candidate import (
    create_autonomous_authorization_candidate,
)
from app.services.autonomous_authorization_candidate_store import (
    GENESIS_RECORD_HASH,
    AutonomousAuthorizationCandidateDuplicate,
    AutonomousAuthorizationCandidateIntegrityError,
    AutonomousAuthorizationCandidateStore,
)
from app.services.autonomous_proposal_review_audit import (
    verify_autonomous_proposal_review_store,
)
from app.services.autonomous_proposal_review_store import (
    AutonomousProposalReviewStore,
)
from tests.test_autonomous_proposal_review_store import (
    make_decision,
)


def make_candidate(
    tmp_path,
    *,
    number: int = 1,
):
    review_store = AutonomousProposalReviewStore(
        tmp_path / f"reviews-{number}.db"
    )

    decision = make_decision(
        tmp_path,
        proposal_id=(
            f"proposal:candidate-store-{number}"
        ),
        review_decision_id=(
            f"human-review:candidate-store-{number}"
        ),
    )

    review_record = review_store.append(
        decision=decision
    )

    review_audit = (
        verify_autonomous_proposal_review_store(
            review_store
        )
    )

    return create_autonomous_authorization_candidate(
        review_record=review_record,
        review_audit=review_audit,
        authorization_candidate_id=(
            f"authorization-candidate:store-{number}"
        ),
    )


def test_append_and_get_candidate(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    candidate = make_candidate(
        tmp_path
    )

    record = store.append(
        candidate=candidate
    )

    loaded = store.get(
        candidate.authorization_candidate_id
    )

    assert loaded == record
    assert record.sequence_number == 1

    assert (
        record.previous_record_hash
        == GENESIS_RECORD_HASH
    )

    assert record.verify_hash() is True
    assert record.can_execute is False


def test_record_contains_candidate_bindings(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    candidate = make_candidate(
        tmp_path
    )

    record = store.append(
        candidate=candidate
    )

    assert (
        record.authorization_candidate_id
        == candidate.authorization_candidate_id
    )

    assert (
        record.candidate_fingerprint
        == candidate.candidate_fingerprint
    )

    assert (
        record.review_record_hash
        == candidate.review_record_hash
    )

    assert (
        record.proposal_id
        == candidate.proposal_id
    )


def test_duplicate_candidate_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    candidate = make_candidate(
        tmp_path
    )

    store.append(
        candidate=candidate
    )

    with pytest.raises(
        AutonomousAuthorizationCandidateDuplicate,
    ):
        store.append(
            candidate=candidate
        )


def test_chain_links_multiple_records(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    first = store.append(
        candidate=make_candidate(
            tmp_path,
            number=1,
        )
    )

    second = store.append(
        candidate=make_candidate(
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


def test_list_count_and_get_by_proposal(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    candidates = [
        make_candidate(
            tmp_path,
            number=number,
        )
        for number in range(
            1,
            4,
        )
    ]

    for candidate in candidates:
        store.append(
            candidate=candidate
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

    loaded = store.get_by_proposal_id(
        candidates[1].proposal_id
    )

    assert loaded is not None

    assert (
        loaded.authorization_candidate_id
        == candidates[1]
        .authorization_candidate_id
    )


def test_invalid_candidate_type_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    with pytest.raises(
        TypeError,
        match=(
            "AutonomousAuthorizationReviewCandidate"
        ),
    ):
        store.append(
            candidate="invalid"
        )


def test_tampered_candidate_fingerprint_rejected(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    candidate = make_candidate(
        tmp_path
    )

    tampered = replace(
        candidate
    )

    object.__setattr__(
        tampered,
        "candidate_fingerprint",
        "f" * 64,
    )

    with pytest.raises(
        AutonomousAuthorizationCandidateIntegrityError,
        match="fingerprint mismatch",
    ):
        store.append(
            candidate=tampered
        )


def test_tampered_payload_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    candidate = make_candidate(
        tmp_path
    )

    store.append(
        candidate=candidate
    )

    with sqlite3.connect(
        database
    ) as connection:
        connection.execute(
            """
            UPDATE
                autonomous_authorization_candidate_records
            SET candidate_payload = ?
            WHERE sequence_number = 1
            """,
            (
                '{"tampered":true}',
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousAuthorizationCandidateIntegrityError,
        match="hash mismatch",
    ):
        store.get(
            candidate.authorization_candidate_id
        )


def test_broken_previous_hash_detected(
    tmp_path,
) -> None:
    database = tmp_path / "candidates.db"

    store = AutonomousAuthorizationCandidateStore(
        database
    )

    store.append(
        candidate=make_candidate(
            tmp_path,
            number=1,
        )
    )

    store.append(
        candidate=make_candidate(
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
                autonomous_authorization_candidate_records
            SET previous_record_hash = ?
            WHERE sequence_number = 2
            """,
            (
                "a" * 64,
            ),
        )

        connection.commit()

    with pytest.raises(
        AutonomousAuthorizationCandidateIntegrityError,
    ):
        store.verify_chain()


def test_record_safety_metadata(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    record = store.append(
        candidate=make_candidate(
            tmp_path
        )
    )

    payload = record.to_dict()

    assert payload["can_execute"] is False

    assert payload["safety"] == {
        "immutable_record": True,
        "append_only": True,
        "authorization_candidate_only": True,
        "authorization_created": False,
        "authorization_token_created": False,
        "approval_claim_created": False,
        "execution_lease_created": False,
        "execution_approved": False,
        "simulation_started": False,
        "network_io_performed": False,
        "device_command_executed": False,
    }


def test_empty_store_chain_is_valid(
    tmp_path,
) -> None:
    store = AutonomousAuthorizationCandidateStore(
        tmp_path / "candidates.db"
    )

    assert store.count() == 0
    assert store.verify_chain() is True
