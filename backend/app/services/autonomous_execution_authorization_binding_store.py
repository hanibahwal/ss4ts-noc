from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from app.models.autonomous_execution_authorization_binding import (
    AutonomousExecutionAuthorizationBinding,
)


DEFAULT_AUTONOMOUS_EXECUTION_AUTHORIZATION_BINDING_DATABASE = Path(
    "backend/data/"
    "autonomous-execution-authorization-bindings.db"
)


class AutonomousExecutionAuthorizationBindingStoreError(
    RuntimeError
):
    """Base immutable binding-store error."""


class AutonomousExecutionAuthorizationBindingDuplicate(
    AutonomousExecutionAuthorizationBindingStoreError
):
    """The binding or its protected identity already exists."""


class AutonomousExecutionAuthorizationBindingIntegrityError(
    AutonomousExecutionAuthorizationBindingStoreError
):
    """Stored binding integrity verification failed."""


def canonical_binding_record_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def calculate_binding_record_hash(
    *,
    sequence_number: int,
    binding_id: str,
    authorization_intent_id: str,
    intent_record_hash: str,
    intent_bridge_fingerprint: str,
    intent_audit_id: str,
    execution_authorization_id: str,
    plan_id: str,
    decision_id: str,
    risk_class: str,
    authorization_status: str,
    authorization_decision: str,
    binding_fingerprint: str,
    binding_payload: dict[str, Any],
    stored_at: str,
    previous_record_hash: str | None,
) -> str:
    payload = {
        "sequence_number":
            sequence_number,
        "binding_id":
            binding_id,
        "authorization_intent_id":
            authorization_intent_id,
        "intent_record_hash":
            intent_record_hash,
        "intent_bridge_fingerprint":
            intent_bridge_fingerprint,
        "intent_audit_id":
            intent_audit_id,
        "execution_authorization_id":
            execution_authorization_id,
        "plan_id":
            plan_id,
        "decision_id":
            decision_id,
        "risk_class":
            risk_class,
        "authorization_status":
            authorization_status,
        "authorization_decision":
            authorization_decision,
        "binding_fingerprint":
            binding_fingerprint,
        "binding_payload":
            binding_payload,
        "stored_at":
            stored_at,
        "previous_record_hash":
            previous_record_hash,
    }

    return hashlib.sha256(
        canonical_binding_record_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousExecutionAuthorizationBindingRecord:
    sequence_number: int

    binding_id: str
    authorization_intent_id: str
    intent_record_hash: str
    intent_bridge_fingerprint: str
    intent_audit_id: str

    execution_authorization_id: str
    plan_id: str
    decision_id: str

    risk_class: str
    authorization_status: str
    authorization_decision: str

    binding_fingerprint: str
    binding_payload: dict[str, Any]

    stored_at: str
    previous_record_hash: str | None
    record_hash: str

    @property
    def execution_authorization_created(
        self,
    ) -> bool:
        return True

    @property
    def authorization_approved(
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
        expected = calculate_binding_record_hash(
            sequence_number=self.sequence_number,
            binding_id=self.binding_id,
            authorization_intent_id=(
                self.authorization_intent_id
            ),
            intent_record_hash=(
                self.intent_record_hash
            ),
            intent_bridge_fingerprint=(
                self.intent_bridge_fingerprint
            ),
            intent_audit_id=self.intent_audit_id,
            execution_authorization_id=(
                self.execution_authorization_id
            ),
            plan_id=self.plan_id,
            decision_id=self.decision_id,
            risk_class=self.risk_class,
            authorization_status=(
                self.authorization_status
            ),
            authorization_decision=(
                self.authorization_decision
            ),
            binding_fingerprint=(
                self.binding_fingerprint
            ),
            binding_payload=self.binding_payload,
            stored_at=self.stored_at,
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
            "binding_id":
                self.binding_id,
            "authorization_intent_id":
                self.authorization_intent_id,
            "intent_record_hash":
                self.intent_record_hash,
            "intent_bridge_fingerprint":
                self.intent_bridge_fingerprint,
            "intent_audit_id":
                self.intent_audit_id,
            "execution_authorization_id":
                self.execution_authorization_id,
            "plan_id":
                self.plan_id,
            "decision_id":
                self.decision_id,
            "risk_class":
                self.risk_class,
            "authorization_status":
                self.authorization_status,
            "authorization_decision":
                self.authorization_decision,
            "binding_fingerprint":
                self.binding_fingerprint,
            "binding_payload":
                dict(
                    self.binding_payload
                ),
            "stored_at":
                self.stored_at,
            "previous_record_hash":
                self.previous_record_hash,
            "record_hash":
                self.record_hash,
            "execution_authorization_created":
                True,
            "authorization_binding_created":
                True,
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
            "can_execute":
                False,
            "safety": {
                "immutable_record":
                    True,
                "append_only":
                    True,
                "authorization_binding_only":
                    True,
                "execution_authorization_created":
                    True,
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
                "authorization_consumed":
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


class AutonomousExecutionAuthorizationBindingStore:
    """
    Immutable append-only execution authorization binding ledger.

    This store records binding evidence only. It never approves,
    consumes, leases, simulates, or executes an authorization.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTONOMOUS_EXECUTION_AUTHORIZATION_BINDING_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Binding database path must not be empty"
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
                autonomous_execution_authorization_binding_records
                (
                    sequence_number
                        INTEGER PRIMARY KEY AUTOINCREMENT,

                    binding_id
                        TEXT NOT NULL UNIQUE,

                    authorization_intent_id
                        TEXT NOT NULL UNIQUE,

                    intent_record_hash
                        TEXT NOT NULL UNIQUE,

                    intent_bridge_fingerprint
                        TEXT NOT NULL,

                    intent_audit_id
                        TEXT NOT NULL,

                    execution_authorization_id
                        TEXT NOT NULL UNIQUE,

                    plan_id
                        TEXT NOT NULL,

                    decision_id
                        TEXT NOT NULL,

                    risk_class
                        TEXT NOT NULL,

                    authorization_status
                        TEXT NOT NULL,

                    authorization_decision
                        TEXT NOT NULL,

                    binding_fingerprint
                        TEXT NOT NULL UNIQUE,

                    binding_payload
                        TEXT NOT NULL,

                    stored_at
                        TEXT NOT NULL,

                    previous_record_hash
                        TEXT,

                    record_hash
                        TEXT NOT NULL UNIQUE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_autonomous_execution_binding_intent
                ON autonomous_execution_authorization_binding_records
                (
                    authorization_intent_id
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_autonomous_execution_binding_authorization
                ON autonomous_execution_authorization_binding_records
                (
                    execution_authorization_id
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_binding(
        binding: AutonomousExecutionAuthorizationBinding,
    ) -> None:
        if not isinstance(
            binding,
            AutonomousExecutionAuthorizationBinding,
        ):
            raise TypeError(
                "binding must be an "
                "AutonomousExecutionAuthorizationBinding"
            )

        if (
            binding.binding_fingerprint
            != binding.calculate_fingerprint()
        ):
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Binding fingerprint is invalid"
            )

        if binding.intent_audit_valid is not True:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Binding intent audit is invalid"
            )

        if binding.authorization_approved:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Approved bindings cannot be stored"
            )

        if binding.authorization_token_created:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Token-bearing bindings cannot be stored"
            )

        if binding.approval_claim_created:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Claim-bearing bindings cannot be stored"
            )

        if binding.execution_lease_created:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Leased bindings cannot be stored"
            )

        if binding.execution_allowed or binding.can_execute:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Executable bindings cannot be stored"
            )

        payload = binding.to_dict()

        if payload.get(
            "authorization_approved"
        ) is not False:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Binding payload claims approval"
            )

        if payload.get(
            "execution_allowed"
        ) is not False:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Binding payload allows execution"
            )

        if payload.get(
            "can_execute"
        ) is not False:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Binding payload is executable"
            )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> AutonomousExecutionAuthorizationBindingRecord:
        try:
            binding_payload = json.loads(
                row["binding_payload"]
            )
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Stored binding payload is invalid"
            ) from exc

        if not isinstance(
            binding_payload,
            dict,
        ):
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Stored binding payload must be an object"
            )

        return AutonomousExecutionAuthorizationBindingRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            binding_id=str(
                row["binding_id"]
            ),
            authorization_intent_id=str(
                row["authorization_intent_id"]
            ),
            intent_record_hash=str(
                row["intent_record_hash"]
            ),
            intent_bridge_fingerprint=str(
                row["intent_bridge_fingerprint"]
            ),
            intent_audit_id=str(
                row["intent_audit_id"]
            ),
            execution_authorization_id=str(
                row["execution_authorization_id"]
            ),
            plan_id=str(
                row["plan_id"]
            ),
            decision_id=str(
                row["decision_id"]
            ),
            risk_class=str(
                row["risk_class"]
            ),
            authorization_status=str(
                row["authorization_status"]
            ),
            authorization_decision=str(
                row["authorization_decision"]
            ),
            binding_fingerprint=str(
                row["binding_fingerprint"]
            ),
            binding_payload=binding_payload,
            stored_at=str(
                row["stored_at"]
            ),
            previous_record_hash=(
                str(
                    row["previous_record_hash"]
                )
                if row["previous_record_hash"]
                is not None
                else None
            ),
            record_hash=str(
                row["record_hash"]
            ),
        )

    def append(
        self,
        *,
        binding: AutonomousExecutionAuthorizationBinding,
        stored_at: datetime | None = None,
    ) -> AutonomousExecutionAuthorizationBindingRecord:
        self._validate_binding(
            binding
        )

        normalized_stored_at = (
            stored_at
            or datetime.now(
                timezone.utc
            )
        )

        if not isinstance(
            normalized_stored_at,
            datetime,
        ):
            raise TypeError(
                "stored_at must be a datetime"
            )

        if (
            normalized_stored_at.tzinfo is None
            or normalized_stored_at.utcoffset() is None
        ):
            raise ValueError(
                "stored_at must be timezone-aware"
            )

        stored_at_text = (
            normalized_stored_at
            .astimezone(
                timezone.utc
            )
            .isoformat()
        )

        binding_payload = binding.to_dict()

        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            latest = connection.execute(
                """
                SELECT
                    sequence_number,
                    record_hash
                FROM
                    autonomous_execution_authorization_binding_records
                ORDER BY
                    sequence_number DESC
                LIMIT 1
                """
            ).fetchone()

            previous_record_hash = (
                str(
                    latest["record_hash"]
                )
                if latest is not None
                else None
            )

            sequence_number = (
                int(
                    latest["sequence_number"]
                ) + 1
                if latest is not None
                else 1
            )

            record_hash = calculate_binding_record_hash(
                sequence_number=sequence_number,
                binding_id=binding.binding_id,
                authorization_intent_id=(
                    binding.authorization_intent_id
                ),
                intent_record_hash=(
                    binding.intent_record_hash
                ),
                intent_bridge_fingerprint=(
                    binding.intent_bridge_fingerprint
                ),
                intent_audit_id=(
                    binding.intent_audit_id
                ),
                execution_authorization_id=(
                    binding.execution_authorization_id
                ),
                plan_id=binding.plan_id,
                decision_id=binding.decision_id,
                risk_class=(
                    binding.risk_class.value
                ),
                authorization_status=(
                    binding.authorization_status.value
                ),
                authorization_decision=(
                    binding.authorization_decision.value
                ),
                binding_fingerprint=(
                    binding.binding_fingerprint
                ),
                binding_payload=binding_payload,
                stored_at=stored_at_text,
                previous_record_hash=(
                    previous_record_hash
                ),
            )

            try:
                connection.execute(
                    """
                    INSERT INTO
                    autonomous_execution_authorization_binding_records
                    (
                        sequence_number,
                        binding_id,
                        authorization_intent_id,
                        intent_record_hash,
                        intent_bridge_fingerprint,
                        intent_audit_id,
                        execution_authorization_id,
                        plan_id,
                        decision_id,
                        risk_class,
                        authorization_status,
                        authorization_decision,
                        binding_fingerprint,
                        binding_payload,
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
                        binding.binding_id,
                        binding.authorization_intent_id,
                        binding.intent_record_hash,
                        binding.intent_bridge_fingerprint,
                        binding.intent_audit_id,
                        binding.execution_authorization_id,
                        binding.plan_id,
                        binding.decision_id,
                        binding.risk_class.value,
                        binding.authorization_status.value,
                        binding.authorization_decision.value,
                        binding.binding_fingerprint,
                        canonical_binding_record_json(
                            binding_payload
                        ),
                        stored_at_text,
                        previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                raise AutonomousExecutionAuthorizationBindingDuplicate(
                    "Execution authorization binding "
                    "already exists"
                ) from exc

            row = connection.execute(
                """
                SELECT *
                FROM
                    autonomous_execution_authorization_binding_records
                WHERE
                    sequence_number = ?
                """,
                (
                    sequence_number,
                ),
            ).fetchone()

        if row is None:
            raise AutonomousExecutionAuthorizationBindingStoreError(
                "Stored binding record could not be read"
            )

        record = self._record_from_row(
            row
        )

        if not record.verify_hash():
            raise AutonomousExecutionAuthorizationBindingIntegrityError(
                "Stored binding record hash is invalid"
            )

        return record

    def get(
        self,
        sequence_number: int,
    ) -> AutonomousExecutionAuthorizationBindingRecord | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM
                    autonomous_execution_authorization_binding_records
                WHERE
                    sequence_number = ?
                """,
                (
                    int(
                        sequence_number
                    ),
                ),
            ).fetchone()

        return (
            self._record_from_row(
                row
            )
            if row is not None
            else None
        )

    def get_by_binding_id(
        self,
        binding_id: str,
    ) -> AutonomousExecutionAuthorizationBindingRecord | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM
                    autonomous_execution_authorization_binding_records
                WHERE
                    binding_id = ?
                """,
                (
                    str(
                        binding_id
                    ).strip(),
                ),
            ).fetchone()

        return (
            self._record_from_row(
                row
            )
            if row is not None
            else None
        )

    def get_by_authorization_intent_id(
        self,
        authorization_intent_id: str,
    ) -> AutonomousExecutionAuthorizationBindingRecord | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM
                    autonomous_execution_authorization_binding_records
                WHERE
                    authorization_intent_id = ?
                """,
                (
                    str(
                        authorization_intent_id
                    ).strip(),
                ),
            ).fetchone()

        return (
            self._record_from_row(
                row
            )
            if row is not None
            else None
        )

    def get_by_execution_authorization_id(
        self,
        execution_authorization_id: str,
    ) -> AutonomousExecutionAuthorizationBindingRecord | None:
        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM
                    autonomous_execution_authorization_binding_records
                WHERE
                    execution_authorization_id = ?
                """,
                (
                    str(
                        execution_authorization_id
                    ).strip(),
                ),
            ).fetchone()

        return (
            self._record_from_row(
                row
            )
            if row is not None
            else None
        )

    def list_records(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[
        AutonomousExecutionAuthorizationBindingRecord
    ]:
        normalized_limit = max(
            1,
            min(
                int(
                    limit
                ),
                1000,
            ),
        )

        normalized_offset = max(
            0,
            int(
                offset
            ),
        )

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM
                    autonomous_execution_authorization_binding_records
                ORDER BY
                    sequence_number ASC
                LIMIT ?
                OFFSET ?
                """,
                (
                    normalized_limit,
                    normalized_offset,
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
                SELECT COUNT(*) AS record_count
                FROM
                    autonomous_execution_authorization_binding_records
                """
            ).fetchone()

        return int(
            row["record_count"]
            if row is not None
            else 0
        )

    def verify_chain(
        self,
    ) -> bool:
        records = self.list_records(
            limit=1000
        )

        previous_hash: str | None = None
        expected_sequence = 1

        for record in records:
            if (
                record.sequence_number
                != expected_sequence
            ):
                return False

            if (
                record.previous_record_hash
                != previous_hash
            ):
                return False

            if not record.verify_hash():
                return False

            payload = record.binding_payload

            if (
                payload.get(
                    "binding_id"
                )
                != record.binding_id
            ):
                return False

            if (
                payload.get(
                    "binding_fingerprint"
                )
                != record.binding_fingerprint
            ):
                return False

            if (
                payload.get(
                    "authorization_intent_id"
                )
                != record.authorization_intent_id
            ):
                return False

            if (
                payload.get(
                    "execution_authorization_id"
                )
                != record.execution_authorization_id
            ):
                return False

            if payload.get(
                "authorization_approved"
            ) is not False:
                return False

            if payload.get(
                "execution_allowed"
            ) is not False:
                return False

            if payload.get(
                "can_execute"
            ) is not False:
                return False

            previous_hash = (
                record.record_hash
            )
            expected_sequence += 1

        return True
