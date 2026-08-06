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

from app.models.autonomous_authorization_intent import (
    AutonomousAuthorizationIntent,
)


DEFAULT_AUTONOMOUS_AUTHORIZATION_INTENT_DATABASE = Path(
    os.getenv(
        "SS4TS_AUTONOMOUS_AUTHORIZATION_INTENT_DB",
        str(
            Path(
                os.getenv(
                    "SS4TS_DATA_DIR",
                    "./data",
                )
            )
            / "autonomous-authorization-intents.db"
        ),
    )
)

GENESIS_RECORD_HASH = "0" * 64


class AutonomousAuthorizationIntentStoreError(
    RuntimeError
):
    """Base authorization intent store error."""


class AutonomousAuthorizationIntentDuplicate(
    AutonomousAuthorizationIntentStoreError
):
    """Intent identity or immutable binding already exists."""


class AutonomousAuthorizationIntentIntegrityError(
    AutonomousAuthorizationIntentStoreError
):
    """Authorization intent record failed integrity checks."""


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


def _intent_record_hash(
    *,
    sequence_number: int,
    authorization_intent_id: str,
    bridge_fingerprint: str,
    authorization_request_id: str,
    request_record_hash: str,
    request_fingerprint: str,
    request_audit_id: str,
    request_audit_valid: bool,
    authorization_candidate_id: str,
    candidate_record_hash: str,
    candidate_fingerprint: str,
    proposal_id: str,
    proposal_record_hash: str,
    intent_payload: dict[str, Any],
    stored_at: str,
    previous_record_hash: str,
) -> str:
    payload = {
        "sequence_number":
            int(sequence_number),
        "authorization_intent_id":
            authorization_intent_id,
        "bridge_fingerprint":
            bridge_fingerprint,
        "authorization_request_id":
            authorization_request_id,
        "request_record_hash":
            request_record_hash,
        "request_fingerprint":
            request_fingerprint,
        "request_audit_id":
            request_audit_id,
        "request_audit_valid":
            bool(request_audit_valid),
        "authorization_candidate_id":
            authorization_candidate_id,
        "candidate_record_hash":
            candidate_record_hash,
        "candidate_fingerprint":
            candidate_fingerprint,
        "proposal_id":
            proposal_id,
        "proposal_record_hash":
            proposal_record_hash,
        "intent_payload":
            intent_payload,
        "stored_at":
            stored_at,
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
class AutonomousAuthorizationIntentRecord:
    sequence_number: int

    authorization_intent_id: str
    bridge_fingerprint: str

    authorization_request_id: str
    request_record_hash: str
    request_fingerprint: str

    request_audit_id: str
    request_audit_valid: bool

    authorization_candidate_id: str
    candidate_record_hash: str
    candidate_fingerprint: str

    proposal_id: str
    proposal_record_hash: str

    intent_payload: dict[str, Any]

    stored_at: str
    previous_record_hash: str
    record_hash: str

    @property
    def execution_authorization_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_allowed(
        self,
    ) -> bool:
        return False

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def verify_hash(
        self,
    ) -> bool:
        expected = _intent_record_hash(
            sequence_number=self.sequence_number,
            authorization_intent_id=(
                self.authorization_intent_id
            ),
            bridge_fingerprint=(
                self.bridge_fingerprint
            ),
            authorization_request_id=(
                self.authorization_request_id
            ),
            request_record_hash=(
                self.request_record_hash
            ),
            request_fingerprint=(
                self.request_fingerprint
            ),
            request_audit_id=(
                self.request_audit_id
            ),
            request_audit_valid=(
                self.request_audit_valid
            ),
            authorization_candidate_id=(
                self.authorization_candidate_id
            ),
            candidate_record_hash=(
                self.candidate_record_hash
            ),
            candidate_fingerprint=(
                self.candidate_fingerprint
            ),
            proposal_id=(
                self.proposal_id
            ),
            proposal_record_hash=(
                self.proposal_record_hash
            ),
            intent_payload=(
                self.intent_payload
            ),
            stored_at=(
                self.stored_at
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
            "authorization_intent_id":
                self.authorization_intent_id,
            "bridge_fingerprint":
                self.bridge_fingerprint,
            "authorization_request_id":
                self.authorization_request_id,
            "request_record_hash":
                self.request_record_hash,
            "request_fingerprint":
                self.request_fingerprint,
            "request_audit_id":
                self.request_audit_id,
            "request_audit_valid":
                self.request_audit_valid,
            "authorization_candidate_id":
                self.authorization_candidate_id,
            "candidate_record_hash":
                self.candidate_record_hash,
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "proposal_id":
                self.proposal_id,
            "proposal_record_hash":
                self.proposal_record_hash,
            "intent":
                self.intent_payload,
            "stored_at":
                self.stored_at,
            "previous_record_hash":
                self.previous_record_hash,
            "record_hash":
                self.record_hash,
            "execution_authorization_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "safety": {
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
            },
        }


class AutonomousAuthorizationIntentStore:
    """
    Immutable append-only authorization intent ledger.

    This store persists non-executable authorization intents only.
    It does not create, approve, or store ExecutionAuthorization,
    tokens, approval claims, execution leases, simulations,
    network operations, or device commands.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_AUTHORIZATION_INTENT_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Authorization intent database "
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
                autonomous_authorization_intent_records
                (
                    sequence_number
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    authorization_intent_id
                        TEXT NOT NULL UNIQUE,

                    bridge_fingerprint
                        TEXT NOT NULL UNIQUE,

                    authorization_request_id
                        TEXT NOT NULL UNIQUE,

                    request_record_hash
                        TEXT NOT NULL UNIQUE,

                    request_fingerprint
                        TEXT NOT NULL UNIQUE,

                    request_audit_id
                        TEXT NOT NULL,

                    request_audit_valid
                        INTEGER NOT NULL,

                    authorization_candidate_id
                        TEXT NOT NULL UNIQUE,

                    candidate_record_hash
                        TEXT NOT NULL,

                    candidate_fingerprint
                        TEXT NOT NULL,

                    proposal_id
                        TEXT NOT NULL UNIQUE,

                    proposal_record_hash
                        TEXT NOT NULL,

                    intent_payload
                        TEXT NOT NULL,

                    stored_at
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
                idx_autonomous_intent_created
                ON autonomous_authorization_intent_records
                (
                    stored_at DESC,
                    sequence_number DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_intent(
        intent: AutonomousAuthorizationIntent,
    ) -> None:
        if not isinstance(
            intent,
            AutonomousAuthorizationIntent,
        ):
            raise TypeError(
                "intent must be an "
                "AutonomousAuthorizationIntent"
            )

        if (
            intent.calculate_fingerprint()
            != intent.bridge_fingerprint
        ):
            raise AutonomousAuthorizationIntentIntegrityError(
                "Authorization intent fingerprint mismatch"
            )

        if intent.request_audit_valid is not True:
            raise AutonomousAuthorizationIntentIntegrityError(
                "Authorization intent request audit is invalid"
            )

        unsafe_claims = (
            "execution_authorization_created",
            "authorization_approved",
            "authorization_token_created",
            "approval_claim_created",
            "execution_lease_created",
            "execution_allowed",
            "can_execute",
        )

        payload = intent.to_dict()

        for field in unsafe_claims:
            if payload.get(field) is not False:
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Authorization intent contains an "
                    f"unsafe claim: {field}"
                )

        safety = payload.get(
            "safety"
        )

        if not isinstance(
            safety,
            dict,
        ):
            raise AutonomousAuthorizationIntentIntegrityError(
                "Authorization intent safety metadata is missing"
            )

        required_safety = {
            "authorization_intent_only": True,
            "request_store_read_only": True,
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

        for field, expected in (
            required_safety.items()
        ):
            if safety.get(field) is not expected:
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Authorization intent safety metadata "
                    f"is invalid: {field}"
                )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousAuthorizationIntentRecord:
        try:
            intent_payload = json.loads(
                row["intent_payload"]
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousAuthorizationIntentIntegrityError(
                "Authorization intent record "
                "contains invalid JSON"
            ) from exc

        if not isinstance(
            intent_payload,
            dict,
        ):
            raise AutonomousAuthorizationIntentIntegrityError(
                "Authorization intent payload "
                "must be a dictionary"
            )

        record = AutonomousAuthorizationIntentRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            authorization_intent_id=str(
                row["authorization_intent_id"]
            ),
            bridge_fingerprint=str(
                row["bridge_fingerprint"]
            ),
            authorization_request_id=str(
                row["authorization_request_id"]
            ),
            request_record_hash=str(
                row["request_record_hash"]
            ),
            request_fingerprint=str(
                row["request_fingerprint"]
            ),
            request_audit_id=str(
                row["request_audit_id"]
            ),
            request_audit_valid=bool(
                row["request_audit_valid"]
            ),
            authorization_candidate_id=str(
                row["authorization_candidate_id"]
            ),
            candidate_record_hash=str(
                row["candidate_record_hash"]
            ),
            candidate_fingerprint=str(
                row["candidate_fingerprint"]
            ),
            proposal_id=str(
                row["proposal_id"]
            ),
            proposal_record_hash=str(
                row["proposal_record_hash"]
            ),
            intent_payload=intent_payload,
            stored_at=str(
                row["stored_at"]
            ),
            previous_record_hash=str(
                row["previous_record_hash"]
            ),
            record_hash=str(
                row["record_hash"]
            ),
        )

        if not record.verify_hash():
            raise AutonomousAuthorizationIntentIntegrityError(
                "Authorization intent record hash mismatch"
            )

        bindings = {
            "authorization_intent_id":
                record.authorization_intent_id,
            "bridge_fingerprint":
                record.bridge_fingerprint,
            "authorization_request_id":
                record.authorization_request_id,
            "request_record_hash":
                record.request_record_hash,
            "request_fingerprint":
                record.request_fingerprint,
            "request_audit_id":
                record.request_audit_id,
            "request_audit_valid":
                record.request_audit_valid,
            "authorization_candidate_id":
                record.authorization_candidate_id,
            "candidate_record_hash":
                record.candidate_record_hash,
            "candidate_fingerprint":
                record.candidate_fingerprint,
            "proposal_id":
                record.proposal_id,
            "proposal_record_hash":
                record.proposal_record_hash,
        }

        for field, expected in bindings.items():
            if intent_payload.get(field) != expected:
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Stored authorization intent payload "
                    f"binding mismatch: {field}"
                )

        if intent_payload.get(
            "can_execute"
        ) is not False:
            raise AutonomousAuthorizationIntentIntegrityError(
                "Stored authorization intent "
                "unexpectedly allows execution"
            )

        return record

    def append(
        self,
        *,
        intent: AutonomousAuthorizationIntent,
    ) -> AutonomousAuthorizationIntentRecord:
        self._validate_intent(
            intent
        )

        intent_payload = intent.to_dict()
        stored_at = _utc_now_text()

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
                        autonomous_authorization_intent_records
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

                record_hash = _intent_record_hash(
                    sequence_number=sequence_number,
                    authorization_intent_id=(
                        intent.authorization_intent_id
                    ),
                    bridge_fingerprint=(
                        intent.bridge_fingerprint
                    ),
                    authorization_request_id=(
                        intent.authorization_request_id
                    ),
                    request_record_hash=(
                        intent.request_record_hash
                    ),
                    request_fingerprint=(
                        intent.request_fingerprint
                    ),
                    request_audit_id=(
                        intent.request_audit_id
                    ),
                    request_audit_valid=(
                        intent.request_audit_valid
                    ),
                    authorization_candidate_id=(
                        intent.authorization_candidate_id
                    ),
                    candidate_record_hash=(
                        intent.candidate_record_hash
                    ),
                    candidate_fingerprint=(
                        intent.candidate_fingerprint
                    ),
                    proposal_id=(
                        intent.proposal_id
                    ),
                    proposal_record_hash=(
                        intent.proposal_record_hash
                    ),
                    intent_payload=intent_payload,
                    stored_at=stored_at,
                    previous_record_hash=(
                        previous_record_hash
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO
                        autonomous_authorization_intent_records
                    (
                        sequence_number,
                        authorization_intent_id,
                        bridge_fingerprint,
                        authorization_request_id,
                        request_record_hash,
                        request_fingerprint,
                        request_audit_id,
                        request_audit_valid,
                        authorization_candidate_id,
                        candidate_record_hash,
                        candidate_fingerprint,
                        proposal_id,
                        proposal_record_hash,
                        intent_payload,
                        stored_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        sequence_number,
                        intent.authorization_intent_id,
                        intent.bridge_fingerprint,
                        intent.authorization_request_id,
                        intent.request_record_hash,
                        intent.request_fingerprint,
                        intent.request_audit_id,
                        int(
                            intent.request_audit_valid
                        ),
                        intent.authorization_candidate_id,
                        intent.candidate_record_hash,
                        intent.candidate_fingerprint,
                        intent.proposal_id,
                        intent.proposal_record_hash,
                        _canonical_json(
                            intent_payload
                        ),
                        stored_at,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                raise AutonomousAuthorizationIntentDuplicate(
                    "Authorization intent ID, fingerprint, "
                    "request, candidate, proposal, or "
                    "record already exists"
                ) from exc

            except Exception:
                connection.rollback()
                raise

        record = self.get(
            intent.authorization_intent_id
        )

        if record is None:
            raise AutonomousAuthorizationIntentIntegrityError(
                "Stored authorization intent "
                "could not be loaded"
            )

        return record

    def get(
        self,
        authorization_intent_id: str,
    ) -> AutonomousAuthorizationIntentRecord | None:
        normalized_id = str(
            authorization_intent_id
        ).strip()

        if not normalized_id:
            raise ValueError(
                "authorization_intent_id "
                "must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM autonomous_authorization_intent_records
                WHERE authorization_intent_id = ?
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

    def get_by_request_id(
        self,
        authorization_request_id: str,
    ) -> AutonomousAuthorizationIntentRecord | None:
        normalized_id = str(
            authorization_request_id
        ).strip()

        if not normalized_id:
            raise ValueError(
                "authorization_request_id "
                "must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM autonomous_authorization_intent_records
                WHERE authorization_request_id = ?
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
    ) -> list[AutonomousAuthorizationIntentRecord]:
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
                FROM autonomous_authorization_intent_records
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
                FROM autonomous_authorization_intent_records
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
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Authorization intent sequence "
                    "is not continuous"
                )

            if (
                record.previous_record_hash
                != expected_previous
            ):
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Authorization intent hash "
                    "chain is broken"
                )

            if not record.verify_hash():
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Authorization intent record "
                    "hash is invalid"
                )

            payload = record.intent_payload

            if (
                payload.get(
                    "bridge_fingerprint"
                )
                != record.bridge_fingerprint
            ):
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Stored authorization intent "
                    "fingerprint mismatch"
                )

            if (
                payload.get(
                    "request_audit_valid"
                )
                is not True
            ):
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Stored authorization intent "
                    "request audit is invalid"
                )

            if payload.get(
                "can_execute"
            ) is not False:
                raise AutonomousAuthorizationIntentIntegrityError(
                    "Stored authorization intent "
                    "unexpectedly allows execution"
                )

            expected_previous = (
                record.record_hash
            )

            expected_sequence += 1

        return True
