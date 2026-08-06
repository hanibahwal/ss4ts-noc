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

from app.models.autonomous_authorization_request import (
    AutonomousControlledAuthorizationRequest,
)


DEFAULT_AUTONOMOUS_AUTHORIZATION_REQUEST_DATABASE = Path(
    os.getenv(
        "SS4TS_AUTONOMOUS_AUTHORIZATION_REQUEST_DB",
        str(
            Path(
                os.getenv(
                    "SS4TS_DATA_DIR",
                    "./data",
                )
            )
            / "autonomous-authorization-requests.db"
        ),
    )
)

GENESIS_RECORD_HASH = "0" * 64


class AutonomousAuthorizationRequestStoreError(
    RuntimeError
):
    """Base authorization request store error."""


class AutonomousAuthorizationRequestDuplicate(
    AutonomousAuthorizationRequestStoreError
):
    """Authorization request identity already exists."""


class AutonomousAuthorizationRequestIntegrityError(
    AutonomousAuthorizationRequestStoreError
):
    """Authorization request failed integrity checks."""


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


def _request_record_hash(
    *,
    sequence_number: int,
    authorization_request_id: str,
    request_fingerprint: str,
    authorization_candidate_id: str,
    candidate_record_hash: str,
    candidate_fingerprint: str,
    review_decision_id: str,
    review_record_hash: str,
    proposal_id: str,
    proposal_record_hash: str,
    candidate_audit_id: str,
    candidate_audit_valid: bool,
    requester_id: str,
    requested_at: str,
    request_reason: str,
    risk_class: str,
    dry_run_required: bool,
    rollback_required: bool,
    verification_required: bool,
    request_payload: dict[str, Any],
    stored_at: str,
    previous_record_hash: str,
) -> str:
    payload = {
        "sequence_number":
            int(sequence_number),
        "authorization_request_id":
            authorization_request_id,
        "request_fingerprint":
            request_fingerprint,
        "authorization_candidate_id":
            authorization_candidate_id,
        "candidate_record_hash":
            candidate_record_hash,
        "candidate_fingerprint":
            candidate_fingerprint,
        "review_decision_id":
            review_decision_id,
        "review_record_hash":
            review_record_hash,
        "proposal_id":
            proposal_id,
        "proposal_record_hash":
            proposal_record_hash,
        "candidate_audit_id":
            candidate_audit_id,
        "candidate_audit_valid":
            bool(
                candidate_audit_valid
            ),
        "requester_id":
            requester_id,
        "requested_at":
            requested_at,
        "request_reason":
            request_reason,
        "risk_class":
            risk_class,
        "dry_run_required":
            bool(
                dry_run_required
            ),
        "rollback_required":
            bool(
                rollback_required
            ),
        "verification_required":
            bool(
                verification_required
            ),
        "request_payload":
            request_payload,
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
class AutonomousAuthorizationRequestRecord:
    sequence_number: int

    authorization_request_id: str
    request_fingerprint: str

    authorization_candidate_id: str
    candidate_record_hash: str
    candidate_fingerprint: str

    review_decision_id: str
    review_record_hash: str

    proposal_id: str
    proposal_record_hash: str

    candidate_audit_id: str
    candidate_audit_valid: bool

    requester_id: str
    requested_at: str
    request_reason: str

    risk_class: str

    dry_run_required: bool
    rollback_required: bool
    verification_required: bool

    request_payload: dict[str, Any]

    stored_at: str
    previous_record_hash: str
    record_hash: str

    @property
    def authorization_created(
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
        expected = _request_record_hash(
            sequence_number=(
                self.sequence_number
            ),
            authorization_request_id=(
                self.authorization_request_id
            ),
            request_fingerprint=(
                self.request_fingerprint
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
            review_decision_id=(
                self.review_decision_id
            ),
            review_record_hash=(
                self.review_record_hash
            ),
            proposal_id=(
                self.proposal_id
            ),
            proposal_record_hash=(
                self.proposal_record_hash
            ),
            candidate_audit_id=(
                self.candidate_audit_id
            ),
            candidate_audit_valid=(
                self.candidate_audit_valid
            ),
            requester_id=(
                self.requester_id
            ),
            requested_at=(
                self.requested_at
            ),
            request_reason=(
                self.request_reason
            ),
            risk_class=(
                self.risk_class
            ),
            dry_run_required=(
                self.dry_run_required
            ),
            rollback_required=(
                self.rollback_required
            ),
            verification_required=(
                self.verification_required
            ),
            request_payload=(
                self.request_payload
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
            "authorization_request_id":
                self.authorization_request_id,
            "request_fingerprint":
                self.request_fingerprint,
            "authorization_candidate_id":
                self.authorization_candidate_id,
            "candidate_record_hash":
                self.candidate_record_hash,
            "candidate_fingerprint":
                self.candidate_fingerprint,
            "review_decision_id":
                self.review_decision_id,
            "review_record_hash":
                self.review_record_hash,
            "proposal_id":
                self.proposal_id,
            "proposal_record_hash":
                self.proposal_record_hash,
            "candidate_audit_id":
                self.candidate_audit_id,
            "candidate_audit_valid":
                self.candidate_audit_valid,
            "requester_id":
                self.requester_id,
            "requested_at":
                self.requested_at,
            "request_reason":
                self.request_reason,
            "risk_class":
                self.risk_class,
            "dry_run_required":
                self.dry_run_required,
            "rollback_required":
                self.rollback_required,
            "verification_required":
                self.verification_required,
            "request_payload":
                self.request_payload,
            "stored_at":
                self.stored_at,
            "previous_record_hash":
                self.previous_record_hash,
            "record_hash":
                self.record_hash,
            "authorization_created":
                False,
            "execution_allowed":
                False,
            "can_execute":
                False,
            "safety": {
                "immutable_record":
                    True,
                "append_only":
                    True,
                "controlled_authorization_request_only":
                    True,
                "execution_authorization_created":
                    False,
                "authorization_approved":
                    False,
                "authorization_token_created":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
                    False,
                "execution_allowed":
                    False,
                "execution_approved":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_access_performed":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            },
        }


class AutonomousAuthorizationRequestStore:
    """
    Immutable append-only controlled authorization request ledger.

    This store does not create or approve ExecutionAuthorization,
    create tokens or claims, acquire leases, simulate, access
    networks or devices, generate commands, or execute actions.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_AUTHORIZATION_REQUEST_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Authorization request database "
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
                autonomous_authorization_request_records
                (
                    sequence_number
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    authorization_request_id
                        TEXT NOT NULL UNIQUE,

                    request_fingerprint
                        TEXT NOT NULL UNIQUE,

                    authorization_candidate_id
                        TEXT NOT NULL UNIQUE,

                    candidate_record_hash
                        TEXT NOT NULL UNIQUE,

                    candidate_fingerprint
                        TEXT NOT NULL,

                    review_decision_id
                        TEXT NOT NULL,

                    review_record_hash
                        TEXT NOT NULL,

                    proposal_id
                        TEXT NOT NULL UNIQUE,

                    proposal_record_hash
                        TEXT NOT NULL,

                    candidate_audit_id
                        TEXT NOT NULL,

                    candidate_audit_valid
                        INTEGER NOT NULL,

                    requester_id
                        TEXT NOT NULL,

                    requested_at
                        TEXT NOT NULL,

                    request_reason
                        TEXT NOT NULL,

                    risk_class
                        TEXT NOT NULL,

                    dry_run_required
                        INTEGER NOT NULL,

                    rollback_required
                        INTEGER NOT NULL,

                    verification_required
                        INTEGER NOT NULL,

                    request_payload
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
                idx_autonomous_authorization_request_stored
                ON autonomous_authorization_request_records
                (
                    stored_at DESC,
                    sequence_number DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_autonomous_authorization_request_requester
                ON autonomous_authorization_request_records
                (
                    requester_id,
                    requested_at DESC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_request(
        request: AutonomousControlledAuthorizationRequest,
    ) -> None:
        if not isinstance(
            request,
            AutonomousControlledAuthorizationRequest,
        ):
            raise TypeError(
                "request must be an "
                "AutonomousControlledAuthorizationRequest"
            )

        if (
            request.calculate_fingerprint()
            != request.request_fingerprint
        ):
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request fingerprint mismatch"
            )

        if request.candidate_audit_valid is not True:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request candidate "
                "audit is not valid"
            )

        if (
            request.authorization_request_created
            is not True
        ):
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request was not created"
            )

        if request.authorization_created:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request already contains "
                "an authorization"
            )

        if request.authorization_approved:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request already claims "
                "approval"
            )

        if request.authorization_token_created:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request already contains "
                "an authorization token"
            )

        if request.execution_lease_created:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request already contains "
                "an execution lease"
            )

        if request.execution_allowed:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request allows execution"
            )

        if request.can_execute:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Executable authorization requests "
                "cannot be stored"
            )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousAuthorizationRequestRecord:
        try:
            payload = json.loads(
                row["request_payload"]
            )

        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request record "
                "contains invalid JSON"
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request payload "
                "must be a dictionary"
            )

        record = AutonomousAuthorizationRequestRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            authorization_request_id=str(
                row["authorization_request_id"]
            ),
            request_fingerprint=str(
                row["request_fingerprint"]
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
            review_decision_id=str(
                row["review_decision_id"]
            ),
            review_record_hash=str(
                row["review_record_hash"]
            ),
            proposal_id=str(
                row["proposal_id"]
            ),
            proposal_record_hash=str(
                row["proposal_record_hash"]
            ),
            candidate_audit_id=str(
                row["candidate_audit_id"]
            ),
            candidate_audit_valid=bool(
                row["candidate_audit_valid"]
            ),
            requester_id=str(
                row["requester_id"]
            ),
            requested_at=str(
                row["requested_at"]
            ),
            request_reason=str(
                row["request_reason"]
            ),
            risk_class=str(
                row["risk_class"]
            ),
            dry_run_required=bool(
                row["dry_run_required"]
            ),
            rollback_required=bool(
                row["rollback_required"]
            ),
            verification_required=bool(
                row["verification_required"]
            ),
            request_payload=payload,
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
            raise AutonomousAuthorizationRequestIntegrityError(
                "Authorization request record "
                "hash mismatch"
            )

        return record

    def append(
        self,
        *,
        request: AutonomousControlledAuthorizationRequest,
    ) -> AutonomousAuthorizationRequestRecord:
        self._validate_request(
            request
        )

        request_payload = request.to_dict()
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
                        autonomous_authorization_request_records
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

                requested_at = (
                    request.requested_at.isoformat()
                )

                risk_class = (
                    request.risk_class.value
                )

                record_hash = _request_record_hash(
                    sequence_number=(
                        sequence_number
                    ),
                    authorization_request_id=(
                        request.authorization_request_id
                    ),
                    request_fingerprint=(
                        request.request_fingerprint
                    ),
                    authorization_candidate_id=(
                        request.authorization_candidate_id
                    ),
                    candidate_record_hash=(
                        request.candidate_record_hash
                    ),
                    candidate_fingerprint=(
                        request.candidate_fingerprint
                    ),
                    review_decision_id=(
                        request.review_decision_id
                    ),
                    review_record_hash=(
                        request.review_record_hash
                    ),
                    proposal_id=(
                        request.proposal_id
                    ),
                    proposal_record_hash=(
                        request.proposal_record_hash
                    ),
                    candidate_audit_id=(
                        request.candidate_audit_id
                    ),
                    candidate_audit_valid=(
                        request.candidate_audit_valid
                    ),
                    requester_id=(
                        request.requester_id
                    ),
                    requested_at=(
                        requested_at
                    ),
                    request_reason=(
                        request.request_reason
                    ),
                    risk_class=(
                        risk_class
                    ),
                    dry_run_required=(
                        request.dry_run_required
                    ),
                    rollback_required=(
                        request.rollback_required
                    ),
                    verification_required=(
                        request.verification_required
                    ),
                    request_payload=(
                        request_payload
                    ),
                    stored_at=(
                        stored_at
                    ),
                    previous_record_hash=(
                        previous_record_hash
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO
                        autonomous_authorization_request_records
                    (
                        sequence_number,
                        authorization_request_id,
                        request_fingerprint,
                        authorization_candidate_id,
                        candidate_record_hash,
                        candidate_fingerprint,
                        review_decision_id,
                        review_record_hash,
                        proposal_id,
                        proposal_record_hash,
                        candidate_audit_id,
                        candidate_audit_valid,
                        requester_id,
                        requested_at,
                        request_reason,
                        risk_class,
                        dry_run_required,
                        rollback_required,
                        verification_required,
                        request_payload,
                        stored_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        sequence_number,
                        request.authorization_request_id,
                        request.request_fingerprint,
                        request.authorization_candidate_id,
                        request.candidate_record_hash,
                        request.candidate_fingerprint,
                        request.review_decision_id,
                        request.review_record_hash,
                        request.proposal_id,
                        request.proposal_record_hash,
                        request.candidate_audit_id,
                        int(
                            request.candidate_audit_valid
                        ),
                        request.requester_id,
                        requested_at,
                        request.request_reason,
                        risk_class,
                        int(
                            request.dry_run_required
                        ),
                        int(
                            request.rollback_required
                        ),
                        int(
                            request.verification_required
                        ),
                        _canonical_json(
                            request_payload
                        ),
                        stored_at,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                raise AutonomousAuthorizationRequestDuplicate(
                    "Authorization request ID, "
                    "request fingerprint, candidate, "
                    "candidate record, proposal, "
                    "or record already exists"
                ) from exc

            except Exception:
                connection.rollback()
                raise

        return AutonomousAuthorizationRequestRecord(
            sequence_number=sequence_number,
            authorization_request_id=(
                request.authorization_request_id
            ),
            request_fingerprint=(
                request.request_fingerprint
            ),
            authorization_candidate_id=(
                request.authorization_candidate_id
            ),
            candidate_record_hash=(
                request.candidate_record_hash
            ),
            candidate_fingerprint=(
                request.candidate_fingerprint
            ),
            review_decision_id=(
                request.review_decision_id
            ),
            review_record_hash=(
                request.review_record_hash
            ),
            proposal_id=(
                request.proposal_id
            ),
            proposal_record_hash=(
                request.proposal_record_hash
            ),
            candidate_audit_id=(
                request.candidate_audit_id
            ),
            candidate_audit_valid=(
                request.candidate_audit_valid
            ),
            requester_id=(
                request.requester_id
            ),
            requested_at=(
                requested_at
            ),
            request_reason=(
                request.request_reason
            ),
            risk_class=(
                risk_class
            ),
            dry_run_required=(
                request.dry_run_required
            ),
            rollback_required=(
                request.rollback_required
            ),
            verification_required=(
                request.verification_required
            ),
            request_payload=(
                request_payload
            ),
            stored_at=stored_at,
            previous_record_hash=(
                previous_record_hash
            ),
            record_hash=record_hash,
        )

    def get(
        self,
        authorization_request_id: str,
    ) -> AutonomousAuthorizationRequestRecord | None:
        normalized = str(
            authorization_request_id
        ).strip()

        if not normalized:
            return None

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM autonomous_authorization_request_records
                WHERE authorization_request_id = ?
                """,
                (
                    normalized,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._record_from_row(
            row
        )

    def get_by_candidate_id(
        self,
        authorization_candidate_id: str,
    ) -> AutonomousAuthorizationRequestRecord | None:
        normalized = str(
            authorization_candidate_id
        ).strip()

        if not normalized:
            return None

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM autonomous_authorization_request_records
                WHERE authorization_candidate_id = ?
                """,
                (
                    normalized,
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
        AutonomousAuthorizationRequestRecord
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
                FROM autonomous_authorization_request_records
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
                FROM autonomous_authorization_request_records
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
                raise AutonomousAuthorizationRequestIntegrityError(
                    "Authorization request sequence "
                    "is not continuous"
                )

            if (
                record.previous_record_hash
                != expected_previous
            ):
                raise AutonomousAuthorizationRequestIntegrityError(
                    "Authorization request hash "
                    "chain is broken"
                )

            if not record.verify_hash():
                raise AutonomousAuthorizationRequestIntegrityError(
                    "Authorization request record "
                    "hash mismatch"
                )

            payload = record.request_payload

            bindings = {
                "authorization_request_id":
                    record.authorization_request_id,
                "request_fingerprint":
                    record.request_fingerprint,
                "authorization_candidate_id":
                    record.authorization_candidate_id,
                "candidate_record_hash":
                    record.candidate_record_hash,
                "candidate_fingerprint":
                    record.candidate_fingerprint,
                "review_decision_id":
                    record.review_decision_id,
                "review_record_hash":
                    record.review_record_hash,
                "proposal_id":
                    record.proposal_id,
                "proposal_record_hash":
                    record.proposal_record_hash,
                "candidate_audit_id":
                    record.candidate_audit_id,
                "requester_id":
                    record.requester_id,
                "requested_at":
                    record.requested_at,
                "request_reason":
                    record.request_reason,
                "risk_class":
                    record.risk_class,
                "dry_run_required":
                    record.dry_run_required,
                "rollback_required":
                    record.rollback_required,
                "verification_required":
                    record.verification_required,
            }

            for field, expected in (
                bindings.items()
            ):
                if payload.get(
                    field
                ) != expected:
                    raise AutonomousAuthorizationRequestIntegrityError(
                        "Stored authorization request "
                        f"payload binding mismatch: {field}"
                    )

            if (
                payload.get(
                    "candidate_audit_valid"
                )
                is not True
            ):
                raise AutonomousAuthorizationRequestIntegrityError(
                    "Stored request candidate audit "
                    "is not valid"
                )

            if (
                payload.get(
                    "authorization_request_created"
                )
                is not True
            ):
                raise AutonomousAuthorizationRequestIntegrityError(
                    "Stored authorization request "
                    "creation claim is invalid"
                )

            false_claims = (
                "authorization_created",
                "authorization_approved",
                "authorization_token_created",
                "execution_lease_created",
                "execution_allowed",
                "can_execute",
            )

            for field in false_claims:
                if payload.get(
                    field
                ) is not False:
                    raise AutonomousAuthorizationRequestIntegrityError(
                        "Stored authorization request "
                        f"safety claim is invalid: {field}"
                    )

            safety = payload.get(
                "safety"
            )

            if not isinstance(
                safety,
                dict,
            ):
                raise AutonomousAuthorizationRequestIntegrityError(
                    "Stored authorization request "
                    "safety metadata is missing"
                )

            required_safety = {
                "controlled_authorization_request_only":
                    True,
                "execution_authorization_created":
                    False,
                "authorization_approved":
                    False,
                "authorization_token_created":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
                    False,
                "execution_allowed":
                    False,
                "execution_approved":
                    False,
                "simulation_started":
                    False,
                "network_io_performed":
                    False,
                "device_access_performed":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            }

            for field, expected in (
                required_safety.items()
            ):
                if safety.get(
                    field
                ) is not expected:
                    raise AutonomousAuthorizationRequestIntegrityError(
                        "Stored request safety "
                        f"metadata mismatch: {field}"
                    )

            expected_previous = (
                record.record_hash
            )

            expected_sequence += 1

        return True
