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

from app.models.autonomous_authorization_candidate import (
    AutonomousAuthorizationReviewCandidate,
)


DEFAULT_AUTONOMOUS_AUTHORIZATION_CANDIDATE_DATABASE = Path(
    os.getenv(
        "SS4TS_AUTONOMOUS_AUTHORIZATION_CANDIDATE_DB",
        str(
            Path(
                os.getenv(
                    "SS4TS_DATA_DIR",
                    "./data",
                )
            )
            / "autonomous-authorization-candidates.db"
        ),
    )
)

GENESIS_RECORD_HASH = "0" * 64


class AutonomousAuthorizationCandidateStoreError(
    RuntimeError
):
    """Base authorization candidate store error."""


class AutonomousAuthorizationCandidateDuplicate(
    AutonomousAuthorizationCandidateStoreError
):
    """Candidate identity or binding already exists."""


class AutonomousAuthorizationCandidateIntegrityError(
    AutonomousAuthorizationCandidateStoreError
):
    """Candidate record failed integrity validation."""


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
    authorization_candidate_id: str,
    candidate_fingerprint: str,
    review_decision_id: str,
    review_record_hash: str,
    decision_fingerprint: str,
    proposal_id: str,
    proposal_record_hash: str,
    queue_item_id: str,
    reviewer_id: str,
    human_decision: str,
    review_audit_id: str,
    candidate_payload: dict[str, Any],
    created_at: str,
    previous_record_hash: str,
) -> str:
    payload = {
        "sequence_number":
            int(sequence_number),
        "authorization_candidate_id":
            authorization_candidate_id,
        "candidate_fingerprint":
            candidate_fingerprint,
        "review_decision_id":
            review_decision_id,
        "review_record_hash":
            review_record_hash,
        "decision_fingerprint":
            decision_fingerprint,
        "proposal_id":
            proposal_id,
        "proposal_record_hash":
            proposal_record_hash,
        "queue_item_id":
            queue_item_id,
        "reviewer_id":
            reviewer_id,
        "human_decision":
            human_decision,
        "review_audit_id":
            review_audit_id,
        "candidate_payload":
            candidate_payload,
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
class AutonomousAuthorizationCandidateRecord:
    sequence_number: int

    authorization_candidate_id: str
    candidate_fingerprint: str

    review_decision_id: str
    review_record_hash: str
    decision_fingerprint: str

    proposal_id: str
    proposal_record_hash: str
    queue_item_id: str

    reviewer_id: str
    human_decision: str
    review_audit_id: str

    candidate_payload: dict[str, Any]

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
            authorization_candidate_id=(
                self.authorization_candidate_id
            ),
            candidate_fingerprint=(
                self.candidate_fingerprint
            ),
            review_decision_id=(
                self.review_decision_id
            ),
            review_record_hash=(
                self.review_record_hash
            ),
            decision_fingerprint=(
                self.decision_fingerprint
            ),
            proposal_id=(
                self.proposal_id
            ),
            proposal_record_hash=(
                self.proposal_record_hash
            ),
            queue_item_id=(
                self.queue_item_id
            ),
            reviewer_id=(
                self.reviewer_id
            ),
            human_decision=(
                self.human_decision
            ),
            review_audit_id=(
                self.review_audit_id
            ),
            candidate_payload=(
                self.candidate_payload
            ),
            created_at=(
                self.created_at
            ),
            previous_record_hash=(
                self.previous_record_hash
            ),
        )

        return expected == self.record_hash

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "sequence_number":
                self.sequence_number,
            "authorization_candidate_id":
                self.authorization_candidate_id,
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "review_decision_id":
                self.review_decision_id,
            "review_record_hash":
                self.review_record_hash,
            "decision_fingerprint":
                self.decision_fingerprint,
            "proposal_id":
                self.proposal_id,
            "proposal_record_hash":
                self.proposal_record_hash,
            "queue_item_id":
                self.queue_item_id,
            "reviewer_id":
                self.reviewer_id,
            "human_decision":
                self.human_decision,
            "review_audit_id":
                self.review_audit_id,
            "candidate_payload":
                self.candidate_payload,
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
                "authorization_candidate_only":
                    True,
                "authorization_created":
                    False,
                "authorization_token_created":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
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


class AutonomousAuthorizationCandidateStore:
    """
    Immutable append-only authorization review candidate ledger.

    This store persists candidates only. It does not create an
    authorization, token, approval claim, execution lease,
    simulation, network operation, or device command.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_AUTHORIZATION_CANDIDATE_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Authorization candidate database "
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

        connection.row_factory = sqlite3.Row

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
                autonomous_authorization_candidate_records
                (
                    sequence_number
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    authorization_candidate_id
                        TEXT NOT NULL UNIQUE,

                    candidate_fingerprint
                        TEXT NOT NULL UNIQUE,

                    review_decision_id
                        TEXT NOT NULL UNIQUE,

                    review_record_hash
                        TEXT NOT NULL UNIQUE,

                    decision_fingerprint
                        TEXT NOT NULL UNIQUE,

                    proposal_id
                        TEXT NOT NULL UNIQUE,

                    proposal_record_hash
                        TEXT NOT NULL,

                    queue_item_id
                        TEXT NOT NULL UNIQUE,

                    reviewer_id
                        TEXT NOT NULL,

                    human_decision
                        TEXT NOT NULL,

                    review_audit_id
                        TEXT NOT NULL,

                    candidate_payload
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
                CREATE INDEX IF NOT EXISTS
                idx_autonomous_candidate_created
                ON autonomous_authorization_candidate_records
                (
                    created_at DESC,
                    sequence_number DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_candidate(
        candidate: AutonomousAuthorizationReviewCandidate,
    ) -> None:
        if not isinstance(
            candidate,
            AutonomousAuthorizationReviewCandidate,
        ):
            raise TypeError(
                "candidate must be an "
                "AutonomousAuthorizationReviewCandidate"
            )

        if (
            candidate.calculate_fingerprint()
            != candidate.candidate_fingerprint
        ):
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Authorization candidate fingerprint mismatch"
            )

        if (
            candidate.eligible_for_authorization_review
            is not True
        ):
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Candidate is not eligible for "
                "authorization review"
            )

        if candidate.review_audit_valid is not True:
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Candidate review audit is not valid"
            )

        if (
            candidate.human_decision
            != "approved_for_authorization_review"
        ):
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Candidate human decision is unsupported"
            )

        if candidate.authorization_created:
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Candidate must not contain an authorization"
            )

        if candidate.approval_claim_created:
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Candidate must not contain an approval claim"
            )

        if candidate.can_execute:
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Executable candidates cannot be stored"
            )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousAuthorizationCandidateRecord:
        try:
            candidate_payload = json.loads(
                row["candidate_payload"]
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Authorization candidate record "
                "contains invalid JSON"
            ) from exc

        if not isinstance(
            candidate_payload,
            dict,
        ):
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Authorization candidate payload "
                "must be a dictionary"
            )

        record = AutonomousAuthorizationCandidateRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            authorization_candidate_id=str(
                row["authorization_candidate_id"]
            ),
            candidate_fingerprint=str(
                row["candidate_fingerprint"]
            ),
            review_decision_id=str(
                row["review_decision_id"]
            ),
            review_record_hash=str(
                row["review_record_hash"]
            ),
            decision_fingerprint=str(
                row["decision_fingerprint"]
            ),
            proposal_id=str(
                row["proposal_id"]
            ),
            proposal_record_hash=str(
                row["proposal_record_hash"]
            ),
            queue_item_id=str(
                row["queue_item_id"]
            ),
            reviewer_id=str(
                row["reviewer_id"]
            ),
            human_decision=str(
                row["human_decision"]
            ),
            review_audit_id=str(
                row["review_audit_id"]
            ),
            candidate_payload=(
                candidate_payload
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
            raise AutonomousAuthorizationCandidateIntegrityError(
                "Authorization candidate record "
                "hash mismatch"
            )

        return record

    def append(
        self,
        *,
        candidate: AutonomousAuthorizationReviewCandidate,
    ) -> AutonomousAuthorizationCandidateRecord:
        self._validate_candidate(
            candidate
        )

        candidate_payload = candidate.to_dict()
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
                        autonomous_authorization_candidate_records
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
                            previous["sequence_number"]
                        )
                        + 1
                    )

                    previous_record_hash = str(
                        previous["record_hash"]
                    )

                record_hash = _record_hash(
                    sequence_number=(
                        sequence_number
                    ),
                    authorization_candidate_id=(
                        candidate
                        .authorization_candidate_id
                    ),
                    candidate_fingerprint=(
                        candidate.candidate_fingerprint
                    ),
                    review_decision_id=(
                        candidate.review_decision_id
                    ),
                    review_record_hash=(
                        candidate.review_record_hash
                    ),
                    decision_fingerprint=(
                        candidate.decision_fingerprint
                    ),
                    proposal_id=(
                        candidate.proposal_id
                    ),
                    proposal_record_hash=(
                        candidate.proposal_record_hash
                    ),
                    queue_item_id=(
                        candidate.queue_item_id
                    ),
                    reviewer_id=(
                        candidate.reviewer_id
                    ),
                    human_decision=(
                        candidate.human_decision
                    ),
                    review_audit_id=(
                        candidate.review_audit_id
                    ),
                    candidate_payload=(
                        candidate_payload
                    ),
                    created_at=created_at,
                    previous_record_hash=(
                        previous_record_hash
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO
                        autonomous_authorization_candidate_records
                    (
                        sequence_number,
                        authorization_candidate_id,
                        candidate_fingerprint,
                        review_decision_id,
                        review_record_hash,
                        decision_fingerprint,
                        proposal_id,
                        proposal_record_hash,
                        queue_item_id,
                        reviewer_id,
                        human_decision,
                        review_audit_id,
                        candidate_payload,
                        created_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        sequence_number,
                        candidate
                        .authorization_candidate_id,
                        candidate.candidate_fingerprint,
                        candidate.review_decision_id,
                        candidate.review_record_hash,
                        candidate.decision_fingerprint,
                        candidate.proposal_id,
                        candidate.proposal_record_hash,
                        candidate.queue_item_id,
                        candidate.reviewer_id,
                        candidate.human_decision,
                        candidate.review_audit_id,
                        _canonical_json(
                            candidate_payload
                        ),
                        created_at,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                raise AutonomousAuthorizationCandidateDuplicate(
                    "Authorization candidate ID, "
                    "fingerprint, review decision, "
                    "review record, proposal, queue item, "
                    "or record already exists"
                ) from exc

            except Exception:
                connection.rollback()
                raise

        return AutonomousAuthorizationCandidateRecord(
            sequence_number=sequence_number,
            authorization_candidate_id=(
                candidate.authorization_candidate_id
            ),
            candidate_fingerprint=(
                candidate.candidate_fingerprint
            ),
            review_decision_id=(
                candidate.review_decision_id
            ),
            review_record_hash=(
                candidate.review_record_hash
            ),
            decision_fingerprint=(
                candidate.decision_fingerprint
            ),
            proposal_id=(
                candidate.proposal_id
            ),
            proposal_record_hash=(
                candidate.proposal_record_hash
            ),
            queue_item_id=(
                candidate.queue_item_id
            ),
            reviewer_id=(
                candidate.reviewer_id
            ),
            human_decision=(
                candidate.human_decision
            ),
            review_audit_id=(
                candidate.review_audit_id
            ),
            candidate_payload=(
                candidate_payload
            ),
            created_at=created_at,
            previous_record_hash=(
                previous_record_hash
            ),
            record_hash=record_hash,
        )

    def get(
        self,
        authorization_candidate_id: str,
    ) -> AutonomousAuthorizationCandidateRecord | None:
        normalized_id = str(
            authorization_candidate_id
        ).strip()

        if not normalized_id:
            return None

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM
                    autonomous_authorization_candidate_records
                WHERE authorization_candidate_id = ?
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
    ) -> AutonomousAuthorizationCandidateRecord | None:
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
                FROM
                    autonomous_authorization_candidate_records
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
        AutonomousAuthorizationCandidateRecord
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
                FROM
                    autonomous_authorization_candidate_records
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
                FROM
                    autonomous_authorization_candidate_records
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
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Authorization candidate sequence "
                    "is not continuous"
                )

            if (
                record.previous_record_hash
                != expected_previous
            ):
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Authorization candidate hash "
                    "chain is broken"
                )

            if not record.verify_hash():
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Authorization candidate record "
                    "hash mismatch"
                )

            payload = record.candidate_payload

            bindings = {
                "authorization_candidate_id":
                    record.authorization_candidate_id,
                "candidate_fingerprint":
                    record.candidate_fingerprint,
                "review_decision_id":
                    record.review_decision_id,
                "review_record_hash":
                    record.review_record_hash,
                "decision_fingerprint":
                    record.decision_fingerprint,
                "proposal_id":
                    record.proposal_id,
                "proposal_record_hash":
                    record.proposal_record_hash,
                "queue_item_id":
                    record.queue_item_id,
                "reviewer_id":
                    record.reviewer_id,
                "human_decision":
                    record.human_decision,
                "review_audit_id":
                    record.review_audit_id,
            }

            for field, expected in bindings.items():
                if payload.get(field) != expected:
                    raise AutonomousAuthorizationCandidateIntegrityError(
                        "Stored authorization candidate "
                        f"payload binding mismatch: {field}"
                    )

            if (
                payload.get(
                    "review_audit_valid"
                )
                is not True
            ):
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Stored candidate review audit "
                    "is not valid"
                )

            if (
                payload.get(
                    "eligible_for_authorization_review"
                )
                is not True
            ):
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Stored candidate is not eligible "
                    "for authorization review"
                )

            if (
                payload.get(
                    "authorization_created"
                )
                is not False
            ):
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Stored candidate contains "
                    "an authorization claim"
                )

            if (
                payload.get(
                    "approval_claim_created"
                )
                is not False
            ):
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Stored candidate contains "
                    "an approval claim"
                )

            if (
                payload.get(
                    "can_execute"
                )
                is not False
            ):
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Stored candidate unexpectedly "
                    "allows execution"
                )

            if (
                record.human_decision
                != "approved_for_authorization_review"
            ):
                raise AutonomousAuthorizationCandidateIntegrityError(
                    "Stored candidate human decision "
                    "is unsupported"
                )

            expected_previous = (
                record.record_hash
            )

            expected_sequence += 1

        return True
