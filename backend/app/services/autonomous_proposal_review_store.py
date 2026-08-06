from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

from app.models.autonomous_proposal_review_decision import (
    AutonomousHumanReviewDecisionType,
    AutonomousProposalHumanReviewDecision,
)


DEFAULT_AUTONOMOUS_REVIEW_DATABASE = Path(
    os.getenv(
        "SS4TS_AUTONOMOUS_REVIEW_DB",
        str(
            Path(
                os.getenv(
                    "SS4TS_DATA_DIR",
                    "./data",
                )
            )
            / "autonomous-review-decisions.db"
        ),
    )
)

GENESIS_RECORD_HASH = "0" * 64


class AutonomousProposalReviewStoreError(
    RuntimeError
):
    """Base immutable review store error."""


class AutonomousProposalReviewDuplicate(
    AutonomousProposalReviewStoreError
):
    """Review ID or fingerprint already exists."""


class AutonomousProposalReviewIntegrityError(
    AutonomousProposalReviewStoreError
):
    """Stored review record failed integrity checks."""


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _utc_now_text() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _record_hash(
    *,
    sequence_number: int,
    review_decision_id: str,
    decision_fingerprint: str,
    queue_item_id: str,
    proposal_id: str,
    proposal_record_hash: str,
    reviewer_id: str,
    decision: str,
    decision_payload: dict[str, Any],
    created_at: str,
    previous_record_hash: str,
) -> str:
    payload = {
        "sequence_number":
            int(sequence_number),
        "review_decision_id":
            review_decision_id,
        "decision_fingerprint":
            decision_fingerprint,
        "queue_item_id":
            queue_item_id,
        "proposal_id":
            proposal_id,
        "proposal_record_hash":
            proposal_record_hash,
        "reviewer_id":
            reviewer_id,
        "decision":
            decision,
        "decision_payload":
            decision_payload,
        "created_at":
            created_at,
        "previous_record_hash":
            previous_record_hash,
    }

    return hashlib.sha256(
        _canonical_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousProposalReviewRecord:
    sequence_number: int

    review_decision_id: str
    decision_fingerprint: str

    queue_item_id: str
    proposal_id: str
    proposal_record_hash: str

    reviewer_id: str
    decision: str

    decision_payload: dict[str, Any]

    created_at: str
    previous_record_hash: str
    record_hash: str

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def verify_hash(
        self,
    ) -> bool:
        expected = _record_hash(
            sequence_number=(
                self.sequence_number
            ),
            review_decision_id=(
                self.review_decision_id
            ),
            decision_fingerprint=(
                self.decision_fingerprint
            ),
            queue_item_id=(
                self.queue_item_id
            ),
            proposal_id=(
                self.proposal_id
            ),
            proposal_record_hash=(
                self.proposal_record_hash
            ),
            reviewer_id=(
                self.reviewer_id
            ),
            decision=(
                self.decision
            ),
            decision_payload=(
                self.decision_payload
            ),
            created_at=(
                self.created_at
            ),
            previous_record_hash=(
                self.previous_record_hash
            ),
        )

        return (
            expected
            == self.record_hash
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "sequence_number":
                self.sequence_number,
            "review_decision_id":
                self.review_decision_id,
            "decision_fingerprint":
                self.decision_fingerprint,
            "queue_item_id":
                self.queue_item_id,
            "proposal_id":
                self.proposal_id,
            "proposal_record_hash":
                self.proposal_record_hash,
            "reviewer_id":
                self.reviewer_id,
            "decision":
                self.decision,
            "decision_payload":
                self.decision_payload,
            "created_at":
                self.created_at,
            "previous_record_hash":
                self.previous_record_hash,
            "record_hash":
                self.record_hash,
            "can_execute":
                False,
            "safety": {
                "immutable_record":
                    True,
                "append_only":
                    True,
                "proposal_ledger_modified":
                    False,
                "review_decision_modified":
                    False,
                "approval_claim_created":
                    False,
                "authorization_created":
                    False,
                "execution_approved":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        }


class AutonomousProposalReviewStore:
    """
    Immutable append-only human review decision ledger.

    The store performs local SQLite I/O only. It does not alter
    the proposal ledger, create execution authorizations, claim
    approvals, start simulations, contact devices, or execute
    network commands.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_REVIEW_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Autonomous review database "
                "path must not be empty"
            )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        return connection

    def initialize(
        self,
    ) -> None:
        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                autonomous_proposal_review_records
                (
                    sequence_number
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    review_decision_id
                        TEXT NOT NULL UNIQUE,

                    decision_fingerprint
                        TEXT NOT NULL UNIQUE,

                    queue_item_id
                        TEXT NOT NULL,

                    proposal_id
                        TEXT NOT NULL,

                    proposal_record_hash
                        TEXT NOT NULL,

                    reviewer_id
                        TEXT NOT NULL,

                    decision
                        TEXT NOT NULL,

                    decision_payload
                        TEXT NOT NULL,

                    created_at
                        TEXT NOT NULL,

                    previous_record_hash
                        TEXT NOT NULL,

                    record_hash
                        TEXT NOT NULL UNIQUE
                )
                """
            )

            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_autonomous_review_proposal_once
                ON autonomous_proposal_review_records
                (
                    proposal_id
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_autonomous_review_created
                ON autonomous_proposal_review_records
                (
                    created_at DESC,
                    sequence_number DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_decision(
        decision: (
            AutonomousProposalHumanReviewDecision
        ),
    ) -> None:
        if not isinstance(
            decision,
            AutonomousProposalHumanReviewDecision,
        ):
            raise TypeError(
                "decision must be an "
                "AutonomousProposalHumanReviewDecision"
            )

        if (
            decision.calculate_fingerprint()
            != decision.decision_fingerprint
        ):
            raise AutonomousProposalReviewIntegrityError(
                "Human review decision fingerprint "
                "mismatch"
            )

        if decision.audit_valid is not True:
            raise AutonomousProposalReviewIntegrityError(
                "Human review decision audit "
                "is not valid"
            )

        if decision.authorization_created:
            raise AutonomousProposalReviewIntegrityError(
                "Human review decision must not "
                "contain an authorization"
            )

        if decision.can_execute:
            raise AutonomousProposalReviewIntegrityError(
                "Executable review decisions "
                "cannot be stored"
            )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousProposalReviewRecord:
        try:
            decision_payload = json.loads(
                row["decision_payload"]
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousProposalReviewIntegrityError(
                "Autonomous review record "
                "contains invalid JSON"
            ) from exc

        if not isinstance(
            decision_payload,
            dict,
        ):
            raise AutonomousProposalReviewIntegrityError(
                "Autonomous review payload "
                "must be a dictionary"
            )

        record = AutonomousProposalReviewRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            review_decision_id=str(
                row["review_decision_id"]
            ),
            decision_fingerprint=str(
                row["decision_fingerprint"]
            ),
            queue_item_id=str(
                row["queue_item_id"]
            ),
            proposal_id=str(
                row["proposal_id"]
            ),
            proposal_record_hash=str(
                row["proposal_record_hash"]
            ),
            reviewer_id=str(
                row["reviewer_id"]
            ),
            decision=str(
                row["decision"]
            ),
            decision_payload=(
                decision_payload
            ),
            created_at=str(
                row["created_at"]
            ),
            previous_record_hash=str(
                row["previous_record_hash"]
            ),
            record_hash=str(
                row["record_hash"]
            ),
        )

        if not record.verify_hash():
            raise AutonomousProposalReviewIntegrityError(
                "Autonomous review record "
                "hash mismatch"
            )

        return record

    def append(
        self,
        *,
        decision: (
            AutonomousProposalHumanReviewDecision
        ),
    ) -> AutonomousProposalReviewRecord:
        self._validate_decision(
            decision
        )

        decision_payload = (
            decision.to_dict()
        )

        created_at = _utc_now_text()

        with closing(
            self._connect()
        ) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                previous = connection.execute(
                    """
                    SELECT
                        sequence_number,
                        record_hash
                    FROM
                        autonomous_proposal_review_records
                    ORDER BY sequence_number DESC
                    LIMIT 1
                    """
                ).fetchone()

                if previous is None:
                    sequence_number = 1

                    previous_record_hash = (
                        GENESIS_RECORD_HASH
                    )

                else:
                    sequence_number = (
                        int(
                            previous[
                                "sequence_number"
                            ]
                        )
                        + 1
                    )

                    previous_record_hash = str(
                        previous[
                            "record_hash"
                        ]
                    )

                record_hash = _record_hash(
                    sequence_number=(
                        sequence_number
                    ),
                    review_decision_id=(
                        decision.review_decision_id
                    ),
                    decision_fingerprint=(
                        decision.decision_fingerprint
                    ),
                    queue_item_id=(
                        decision.queue_item_id
                    ),
                    proposal_id=(
                        decision.proposal_id
                    ),
                    proposal_record_hash=(
                        decision.record_hash
                    ),
                    reviewer_id=(
                        decision.reviewer_id
                    ),
                    decision=(
                        decision.decision.value
                    ),
                    decision_payload=(
                        decision_payload
                    ),
                    created_at=created_at,
                    previous_record_hash=(
                        previous_record_hash
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO
                        autonomous_proposal_review_records
                    (
                        sequence_number,
                        review_decision_id,
                        decision_fingerprint,
                        queue_item_id,
                        proposal_id,
                        proposal_record_hash,
                        reviewer_id,
                        decision,
                        decision_payload,
                        created_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        sequence_number,
                        decision.review_decision_id,
                        decision.decision_fingerprint,
                        decision.queue_item_id,
                        decision.proposal_id,
                        decision.record_hash,
                        decision.reviewer_id,
                        decision.decision.value,
                        _canonical_json(
                            decision_payload
                        ),
                        created_at,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                raise AutonomousProposalReviewDuplicate(
                    "Human review decision ID, "
                    "fingerprint, proposal, or "
                    "record already exists"
                ) from exc

            except Exception:
                connection.rollback()
                raise

        return AutonomousProposalReviewRecord(
            sequence_number=(
                sequence_number
            ),
            review_decision_id=(
                decision.review_decision_id
            ),
            decision_fingerprint=(
                decision.decision_fingerprint
            ),
            queue_item_id=(
                decision.queue_item_id
            ),
            proposal_id=(
                decision.proposal_id
            ),
            proposal_record_hash=(
                decision.record_hash
            ),
            reviewer_id=(
                decision.reviewer_id
            ),
            decision=(
                decision.decision.value
            ),
            decision_payload=(
                decision_payload
            ),
            created_at=created_at,
            previous_record_hash=(
                previous_record_hash
            ),
            record_hash=record_hash,
        )

    def get(
        self,
        review_decision_id: str,
    ) -> AutonomousProposalReviewRecord | None:
        normalized_id = str(
            review_decision_id
        ).strip()

        if not normalized_id:
            return None

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM autonomous_proposal_review_records
                WHERE review_decision_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._record_from_row(
            row
        )

    def get_by_proposal_id(
        self,
        proposal_id: str,
    ) -> AutonomousProposalReviewRecord | None:
        normalized_id = str(
            proposal_id
        ).strip()

        if not normalized_id:
            return None

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM autonomous_proposal_review_records
                WHERE proposal_id = ?
                """,
                (
                    normalized_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._record_from_row(
            row
        )

    def list_records(
        self,
        *,
        limit: int = 100,
    ) -> list[
        AutonomousProposalReviewRecord
    ]:
        safe_limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM autonomous_proposal_review_records
                ORDER BY sequence_number ASC
                LIMIT ?
                """,
                (
                    safe_limit,
                ),
            ).fetchall()

        return [
            self._record_from_row(
                row
            )
            for row in rows
        ]

    def count(
        self,
    ) -> int:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM autonomous_proposal_review_records
                """
            ).fetchone()

        return int(
            row["total"]
        )

    def verify_chain(
        self,
    ) -> bool:
        records = self.list_records(
            limit=1000
        )

        expected_previous = (
            GENESIS_RECORD_HASH
        )

        expected_sequence = 1

        for record in records:
            if (
                record.sequence_number
                != expected_sequence
            ):
                raise AutonomousProposalReviewIntegrityError(
                    "Autonomous review sequence "
                    "is not continuous"
                )

            if (
                record.previous_record_hash
                != expected_previous
            ):
                raise AutonomousProposalReviewIntegrityError(
                    "Autonomous review hash "
                    "chain is broken"
                )

            if not record.verify_hash():
                raise AutonomousProposalReviewIntegrityError(
                    "Autonomous review record "
                    "hash mismatch"
                )

            payload_fingerprint = str(
                record.decision_payload.get(
                    "decision_fingerprint",
                    "",
                )
            )

            if (
                payload_fingerprint
                != record.decision_fingerprint
            ):
                raise AutonomousProposalReviewIntegrityError(
                    "Stored review decision "
                    "fingerprint mismatch"
                )

            if (
                record.decision
                not in {
                    item.value
                    for item in (
                        AutonomousHumanReviewDecisionType
                    )
                }
            ):
                raise AutonomousProposalReviewIntegrityError(
                    "Stored review decision type "
                    "is unsupported"
                )

            expected_previous = (
                record.record_hash
            )

            expected_sequence += 1

        return True
