from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import sqlite3

import pytest

from app.models.autonomous_controlled_authorization_human_decision import (
    AutonomousControlledAuthorizationHumanDecision,
)
from app.services.autonomous_controlled_authorization_human_decision_store import (
    AutonomousControlledAuthorizationHumanDecisionStore,
    AutonomousHumanApprovalDecisionDuplicate,
    AutonomousHumanApprovalDecisionIntegrityError,
)
from tests.test_autonomous_controlled_authorization_human_decision import (
    make_verified_candidate,
)
from tests.test_autonomous_execution_authorization_binding_service import (
    NOW,
)


def make_decision(
    tmp_path,
    *,
    suffix: str = "one",
    human_decision: str = "approved",
):
    record, audit = make_verified_candidate(
        tmp_path
        / f"candidate-{suffix}"
    )

    decision = (
        AutonomousControlledAuthorizationHumanDecision
        .from_verified_candidate(
            approval_decision_id=(
                f"approval-decision:store:{suffix}"
            ),
            candidate_record=record,
            candidate_audit=audit,
            reviewer_id=(
                f"reviewer:hani:{suffix}"
            ),
            human_decision=human_decision,
            decision_reason=(
                "Human controlled authorization "
                f"decision {suffix}"
            ),
            decided_at=(
                NOW
                + timedelta(
                    minutes=5
                )
            ),
        )
    )

    if suffix == "one":
        return decision

    def unique_hash(
        value: str,
    ) -> str:
        return hashlib.sha256(
            (
                value
                + ":"
                + suffix
            ).encode("utf-8")
        ).hexdigest()

    values = {
        "approval_decision_id":
            decision.approval_decision_id,
        "approval_candidate_id":
            (
                f"{decision.approval_candidate_id}"
                f":{suffix}"
            ),
        "candidate_record_hash":
            unique_hash(
                decision.candidate_record_hash
            ),
        "candidate_fingerprint":
            unique_hash(
                decision.candidate_fingerprint
            ),
        "candidate_audit_id":
            (
                f"{decision.candidate_audit_id}"
                f":{suffix}"
            ),
        "candidate_audit_valid":
            decision.candidate_audit_valid,
        "binding_id":
            f"{decision.binding_id}:{suffix}",
        "execution_authorization_id":
            (
                f"{decision.execution_authorization_id}"
                f":{suffix}"
            ),
        "plan_id":
            f"{decision.plan_id}:{suffix}",
        "source_decision_id":
            (
                f"{decision.source_decision_id}"
                f":{suffix}"
            ),
        "risk_class":
            decision.risk_class,
        "reviewer_id":
            decision.reviewer_id,
        "human_decision":
            decision.human_decision,
        "decision_reason":
            decision.decision_reason,
        "decided_at":
            decision.decided_at,
    }

    return AutonomousControlledAuthorizationHumanDecision(
        **values,
        decision_fingerprint="",
    )


def append_decision(
    store,
    decision,
):
    return store.append(
        decision=decision,
        stored_at=(
            decision.decided_at
            + timedelta(
                seconds=1
            )
        ),
    )


def test_append_human_decision(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    decision = make_decision(
        tmp_path
    )

    record = append_decision(
        store,
        decision,
    )

    assert record.sequence_number == 1
    assert (
        record.approval_decision_id
        == decision.approval_decision_id
    )
    assert record.verify_hash() is True
    assert store.count() == 1
    assert store.verify_chain() is True


def test_lookup_methods(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    decision = make_decision(
        tmp_path
    )

    record = append_decision(
        store,
        decision,
    )

    assert (
        store.get(
            record.sequence_number
        )
        == record
    )

    assert (
        store.get_by_approval_decision_id(
            record.approval_decision_id
        )
        == record
    )

    assert (
        store.get_by_approval_candidate_id(
            record.approval_candidate_id
        )
        == record
    )

    assert (
        store.get_by_execution_authorization_id(
            record.execution_authorization_id
        )
        == record
    )


def test_missing_record_returns_none(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    assert store.get(999) is None

    assert (
        store.get_by_approval_decision_id(
            "missing"
        )
        is None
    )


def test_duplicate_decision_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    decision = make_decision(
        tmp_path
    )

    append_decision(
        store,
        decision,
    )

    with pytest.raises(
        AutonomousHumanApprovalDecisionDuplicate,
        match="protected identity",
    ):
        append_decision(
            store,
            decision,
        )


def test_two_independent_decisions_form_chain(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    first = append_decision(
        store,
        make_decision(
            tmp_path,
            suffix="first",
        ),
    )

    second = append_decision(
        store,
        make_decision(
            tmp_path,
            suffix="second",
            human_decision="rejected",
        ),
    )

    assert first.sequence_number == 1
    assert second.sequence_number == 2

    assert (
        second.previous_record_hash
        == first.record_hash
    )

    assert store.verify_chain() is True


def test_record_never_allows_execution(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    record = append_decision(
        store,
        make_decision(
            tmp_path
        ),
    )

    payload = record.to_dict()

    assert record.human_decision_recorded is True
    assert record.approved_by_human is True

    assert record.authorization_approved is False
    assert (
        record.authorization_token_created
        is False
    )
    assert record.approval_claim_created is False
    assert record.execution_lease_created is False
    assert record.execution_allowed is False
    assert record.can_execute is False

    assert payload["can_execute"] is False


def test_invalid_decision_type_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    with pytest.raises(
        TypeError,
        match="decision",
    ):
        store.append(
            decision="invalid",
            stored_at=NOW,
        )


def test_naive_stored_at_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    decision = make_decision(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        store.append(
            decision=decision,
            stored_at=datetime(
                2026,
                8,
                6,
                22,
                45,
            ),
        )


def test_stored_at_before_decision_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    decision = make_decision(
        tmp_path
    )

    with pytest.raises(
        ValueError,
        match="earlier",
    ):
        store.append(
            decision=decision,
            stored_at=(
                decision.decided_at
                - timedelta(
                    seconds=1
                )
            ),
        )


def test_tampered_record_hash_breaks_chain(
    tmp_path,
) -> None:
    database = (
        tmp_path / "decisions.db"
    )

    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            database
        )
    )

    append_decision(
        store,
        make_decision(
            tmp_path
        ),
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

    record = store.get(1)

    assert record is not None
    assert record.verify_hash() is False
    assert store.verify_chain() is False


def test_tampered_payload_breaks_chain(
    tmp_path,
) -> None:
    database = (
        tmp_path / "decisions.db"
    )

    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            database
        )
    )

    append_decision(
        store,
        make_decision(
            tmp_path
        ),
    )

    with sqlite3.connect(
        database
    ) as connection:
        row = connection.execute(
            f"""
            SELECT decision_payload
            FROM {store.TABLE_NAME}
            WHERE sequence_number = 1
            """
        ).fetchone()

        payload = json.loads(
            row[0]
        )

        payload["can_execute"] = True

        connection.execute(
            f"""
            UPDATE {store.TABLE_NAME}
            SET decision_payload = ?
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

    assert store.verify_chain() is False


def test_tampered_decision_fingerprint_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    decision = make_decision(
        tmp_path
    )

    object.__setattr__(
        decision,
        "decision_fingerprint",
        "f" * 64,
    )

    with pytest.raises(
        AutonomousHumanApprovalDecisionIntegrityError,
        match="fingerprint mismatch",
    ):
        append_decision(
            store,
            decision,
        )


def test_list_records(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    append_decision(
        store,
        make_decision(
            tmp_path,
            suffix="first",
        ),
    )

    append_decision(
        store,
        make_decision(
            tmp_path,
            suffix="second",
            human_decision="cancelled",
        ),
    )

    records = store.list_records()

    assert len(records) == 2
    assert records[0].sequence_number == 1
    assert records[1].sequence_number == 2


def test_invalid_limit_rejected(
    tmp_path,
) -> None:
    store = (
        AutonomousControlledAuthorizationHumanDecisionStore(
            tmp_path / "decisions.db"
        )
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        store.list_records(
            limit=0
        )
