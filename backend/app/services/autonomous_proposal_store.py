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

from app.models.autonomous_operation_proposal import (
    AutonomousOperationProposal,
)
from app.services.autonomous_proposal_binding import (
    AutonomousProposalBindingResult,
)
from app.services.autonomous_proposal_policy import (
    AutonomousProposalPolicyResult,
)


DEFAULT_AUTONOMOUS_PROPOSAL_DATABASE = Path(
    os.getenv(
        "SS4TS_AUTONOMOUS_PROPOSAL_DB",
        str(
            Path(
                os.getenv(
                    "SS4TS_DATA_DIR",
                    "./data",
                )
            )
            / "autonomous-proposals.db"
        ),
    )
)

GENESIS_RECORD_HASH = "0" * 64


class AutonomousProposalStoreError(RuntimeError):
    """Base autonomous proposal store error."""


class AutonomousProposalDuplicate(
    AutonomousProposalStoreError
):
    """Proposal ID or fingerprint already exists."""


class AutonomousProposalIntegrityError(
    AutonomousProposalStoreError
):
    """Stored immutable record failed verification."""


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


def _proposal_content_fingerprint(
    proposal_payload: dict[str, Any],
) -> str:
    """
    Produce a stable semantic fingerprint.

    Identity and volatile timestamp fields are intentionally
    excluded so identical proposals cannot be reinserted under
    a different proposal ID.
    """
    content = dict(
        proposal_payload
    )

    for field in (
        "proposal_id",
        "created_at",
        "expires_at",
        "fingerprint",
    ):
        content.pop(
            field,
            None,
        )

    safety = content.get(
        "safety"
    )

    if isinstance(
        safety,
        dict,
    ):
        content["safety"] = dict(
            safety
        )

    return hashlib.sha256(
        _canonical_json(
            content
        ).encode("utf-8")
    ).hexdigest()


def _record_hash(
    *,
    sequence_number: int,
    proposal_id: str,
    proposal_fingerprint: str,
    proposal_payload: dict[str, Any],
    policy_payload: dict[str, Any],
    binding_payload: dict[str, Any],
    created_at: str,
    previous_record_hash: str,
) -> str:
    payload = {
        "sequence_number":
            int(sequence_number),
        "proposal_id":
            proposal_id,
        "proposal_fingerprint":
            proposal_fingerprint,
        "proposal_payload":
            proposal_payload,
        "policy_payload":
            policy_payload,
        "binding_payload":
            binding_payload,
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
class AutonomousProposalRecord:
    sequence_number: int
    proposal_id: str
    proposal_fingerprint: str

    proposal_payload: dict[str, Any]
    policy_payload: dict[str, Any]
    binding_payload: dict[str, Any]

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
            proposal_id=(
                self.proposal_id
            ),
            proposal_fingerprint=(
                self.proposal_fingerprint
            ),
            proposal_payload=(
                self.proposal_payload
            ),
            policy_payload=(
                self.policy_payload
            ),
            binding_payload=(
                self.binding_payload
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
            "proposal_id":
                self.proposal_id,
            "proposal_fingerprint":
                self.proposal_fingerprint,
            "proposal":
                self.proposal_payload,
            "policy":
                self.policy_payload,
            "binding":
                self.binding_payload,
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
                "execution_authority":
                    False,
                "authorization_created":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_command_executed":
                    False,
            },
        }


class AutonomousProposalStore:
    """
    Immutable append-only autonomous proposal ledger.

    The store performs local SQLite I/O only. It does not create
    execution authorizations, contact devices, start simulations,
    or execute network commands.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_PROPOSAL_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Autonomous proposal database "
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
                autonomous_proposal_records
                (
                    sequence_number
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    proposal_id
                        TEXT NOT NULL UNIQUE,

                    proposal_fingerprint
                        TEXT NOT NULL UNIQUE,

                    proposal_payload
                        TEXT NOT NULL,

                    policy_payload
                        TEXT NOT NULL,

                    binding_payload
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
                idx_autonomous_proposal_created
                ON autonomous_proposal_records
                (
                    created_at DESC,
                    sequence_number DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_inputs(
        *,
        proposal: AutonomousOperationProposal,
        policy: AutonomousProposalPolicyResult,
        binding: AutonomousProposalBindingResult,
    ) -> None:
        if not isinstance(
            proposal,
            AutonomousOperationProposal,
        ):
            raise TypeError(
                "proposal must be an "
                "AutonomousOperationProposal"
            )

        if not isinstance(
            policy,
            AutonomousProposalPolicyResult,
        ):
            raise TypeError(
                "policy must be an "
                "AutonomousProposalPolicyResult"
            )

        if not isinstance(
            binding,
            AutonomousProposalBindingResult,
        ):
            raise TypeError(
                "binding must be an "
                "AutonomousProposalBindingResult"
            )

        if (
            proposal.proposal_id
            != policy.proposal_id
        ):
            raise ValueError(
                "Policy result proposal ID "
                "does not match proposal"
            )

        if (
            proposal.proposal_id
            != binding.proposal_id
        ):
            raise ValueError(
                "Binding result proposal ID "
                "does not match proposal"
            )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousProposalRecord:
        try:
            proposal_payload = json.loads(
                row["proposal_payload"]
            )

            policy_payload = json.loads(
                row["policy_payload"]
            )

            binding_payload = json.loads(
                row["binding_payload"]
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousProposalIntegrityError(
                "Autonomous proposal record "
                "contains invalid JSON"
            ) from exc

        record = AutonomousProposalRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            proposal_id=str(
                row["proposal_id"]
            ),
            proposal_fingerprint=str(
                row["proposal_fingerprint"]
            ),
            proposal_payload=(
                proposal_payload
            ),
            policy_payload=(
                policy_payload
            ),
            binding_payload=(
                binding_payload
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
            raise AutonomousProposalIntegrityError(
                "Autonomous proposal record "
                "hash mismatch"
            )

        return record

    def append(
        self,
        *,
        proposal: AutonomousOperationProposal,
        policy: AutonomousProposalPolicyResult,
        binding: AutonomousProposalBindingResult,
    ) -> AutonomousProposalRecord:
        self._validate_inputs(
            proposal=proposal,
            policy=policy,
            binding=binding,
        )

        proposal_payload = (
            proposal.to_dict()
        )

        policy_payload = (
            policy.to_dict()
        )

        binding_payload = (
            binding.to_dict()
        )

        proposal_fingerprint = (
            _proposal_content_fingerprint(
                proposal_payload
            )
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
                    FROM autonomous_proposal_records
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
                    proposal_id=(
                        proposal.proposal_id
                    ),
                    proposal_fingerprint=(
                        proposal_fingerprint
                    ),
                    proposal_payload=(
                        proposal_payload
                    ),
                    policy_payload=(
                        policy_payload
                    ),
                    binding_payload=(
                        binding_payload
                    ),
                    created_at=created_at,
                    previous_record_hash=(
                        previous_record_hash
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO
                    autonomous_proposal_records
                    (
                        sequence_number,
                        proposal_id,
                        proposal_fingerprint,
                        proposal_payload,
                        policy_payload,
                        binding_payload,
                        created_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sequence_number,
                        proposal.proposal_id,
                        proposal_fingerprint,
                        _canonical_json(
                            proposal_payload
                        ),
                        _canonical_json(
                            policy_payload
                        ),
                        _canonical_json(
                            binding_payload
                        ),
                        created_at,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                raise AutonomousProposalDuplicate(
                    "Autonomous proposal ID, "
                    "fingerprint, or record "
                    "already exists"
                ) from exc

            except Exception:
                connection.rollback()
                raise

        return AutonomousProposalRecord(
            sequence_number=(
                sequence_number
            ),
            proposal_id=(
                proposal.proposal_id
            ),
            proposal_fingerprint=(
                proposal_fingerprint
            ),
            proposal_payload=(
                proposal_payload
            ),
            policy_payload=(
                policy_payload
            ),
            binding_payload=(
                binding_payload
            ),
            created_at=created_at,
            previous_record_hash=(
                previous_record_hash
            ),
            record_hash=record_hash,
        )

    def get(
        self,
        proposal_id: str,
    ) -> AutonomousProposalRecord | None:
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
                FROM autonomous_proposal_records
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
    ) -> list[AutonomousProposalRecord]:
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
                FROM autonomous_proposal_records
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
                FROM autonomous_proposal_records
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
                raise AutonomousProposalIntegrityError(
                    "Autonomous proposal sequence "
                    "is not continuous"
                )

            if (
                record.previous_record_hash
                != expected_previous
            ):
                raise AutonomousProposalIntegrityError(
                    "Autonomous proposal hash "
                    "chain is broken"
                )

            if not record.verify_hash():
                raise AutonomousProposalIntegrityError(
                    "Autonomous proposal record "
                    "hash mismatch"
                )

            expected_previous = (
                record.record_hash
            )

            expected_sequence += 1

        return True
