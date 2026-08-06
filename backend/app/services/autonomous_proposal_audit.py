from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.services.autonomous_proposal_store import (
    AutonomousProposalRecord,
    AutonomousProposalStore,
    GENESIS_RECORD_HASH,
)


SERVICE_NAME = (
    "SS4TS Autonomous Proposal Audit Verification"
)

SERVICE_VERSION = "1.0.0"


def _utc_now_text() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass(
    frozen=True,
    slots=True,
)
class AutonomousProposalAuditReport:
    audit_id: str
    database_path: str
    verified_at: str

    record_count: int
    verified_record_count: int

    first_sequence: int | None
    last_sequence: int | None

    chain_valid: bool
    sequence_valid: bool
    hashes_valid: bool
    genesis_valid: bool
    payloads_valid: bool

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def audit_valid(
        self,
    ) -> bool:
        return (
            self.chain_valid
            and self.sequence_valid
            and self.hashes_valid
            and self.genesis_valid
            and self.payloads_valid
            and not self.errors
        )

    @property
    def can_execute(
        self,
    ) -> bool:
        return False

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "audit_id":
                self.audit_id,
            "database_path":
                self.database_path,
            "verified_at":
                self.verified_at,
            "record_count":
                self.record_count,
            "verified_record_count":
                self.verified_record_count,
            "first_sequence":
                self.first_sequence,
            "last_sequence":
                self.last_sequence,
            "audit_valid":
                self.audit_valid,
            "checks": {
                "chain_valid":
                    self.chain_valid,
                "sequence_valid":
                    self.sequence_valid,
                "hashes_valid":
                    self.hashes_valid,
                "genesis_valid":
                    self.genesis_valid,
                "payloads_valid":
                    self.payloads_valid,
            },
            "errors":
                list(
                    self.errors
                ),
            "warnings":
                list(
                    self.warnings
                ),
            "can_execute":
                False,
            "service": {
                "name":
                    SERVICE_NAME,
                "version":
                    SERVICE_VERSION,
            },
            "safety": {
                "read_only_audit":
                    True,
                "database_write_performed":
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


class AutonomousProposalAuditVerifier:
    """
    Read-only verification of the autonomous proposal ledger.

    This service does not insert, update, or delete records.
    It does not create execution authorization, perform network
    I/O, start simulation, or execute device commands.
    """

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Audit database path must not be empty"
            )

    def _connect_read_only(
        self,
    ) -> sqlite3.Connection:
        uri = (
            f"file:{self.database_path.resolve()}"
            "?mode=ro"
        )

        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=30,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA query_only = ON"
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return connection

    @staticmethod
    def _decode_payload(
        row: sqlite3.Row,
        field: str,
    ) -> dict[str, Any]:
        value = json.loads(
            row[field]
        )

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                f"{field} must contain a JSON object"
            )

        return value

    @classmethod
    def _record_from_row(
        cls,
        row: sqlite3.Row,
    ) -> AutonomousProposalRecord:
        return AutonomousProposalRecord(
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
                cls._decode_payload(
                    row,
                    "proposal_payload",
                )
            ),
            policy_payload=(
                cls._decode_payload(
                    row,
                    "policy_payload",
                )
            ),
            binding_payload=(
                cls._decode_payload(
                    row,
                    "binding_payload",
                )
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

    def verify(
        self,
    ) -> AutonomousProposalAuditReport:
        errors: list[str] = []
        warnings: list[str] = []

        sequence_valid = True
        hashes_valid = True
        genesis_valid = True
        chain_valid = True
        payloads_valid = True

        verified_record_count = 0
        records: list[AutonomousProposalRecord] = []

        if not self.database_path.exists():
            return AutonomousProposalAuditReport(
                audit_id=(
                    f"autonomous-audit:{uuid4()}"
                ),
                database_path=str(
                    self.database_path
                ),
                verified_at=_utc_now_text(),
                record_count=0,
                verified_record_count=0,
                first_sequence=None,
                last_sequence=None,
                chain_valid=False,
                sequence_valid=False,
                hashes_valid=False,
                genesis_valid=False,
                payloads_valid=False,
                errors=(
                    "Autonomous proposal database "
                    "does not exist",
                ),
                warnings=(),
            )

        try:
            with closing(
                self._connect_read_only()
            ) as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM autonomous_proposal_records
                    ORDER BY sequence_number ASC
                    """
                ).fetchall()

        except sqlite3.Error as exc:
            return AutonomousProposalAuditReport(
                audit_id=(
                    f"autonomous-audit:{uuid4()}"
                ),
                database_path=str(
                    self.database_path
                ),
                verified_at=_utc_now_text(),
                record_count=0,
                verified_record_count=0,
                first_sequence=None,
                last_sequence=None,
                chain_valid=False,
                sequence_valid=False,
                hashes_valid=False,
                genesis_valid=False,
                payloads_valid=False,
                errors=(
                    f"Unable to read autonomous "
                    f"proposal ledger: {exc}",
                ),
                warnings=(),
            )

        for row in rows:
            try:
                record = self._record_from_row(
                    row
                )

            except (
                TypeError,
                ValueError,
                KeyError,
                json.JSONDecodeError,
            ) as exc:
                payloads_valid = False

                errors.append(
                    "Invalid stored payload at "
                    f"sequence "
                    f"{row['sequence_number']}: "
                    f"{exc}"
                )

                continue

            records.append(
                record
            )

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        for index, record in enumerate(
            records
        ):
            if (
                record.sequence_number
                != expected_sequence
            ):
                sequence_valid = False

                errors.append(
                    "Sequence mismatch: expected "
                    f"{expected_sequence}, found "
                    f"{record.sequence_number}"
                )

            if index == 0:
                if (
                    record.previous_record_hash
                    != GENESIS_RECORD_HASH
                ):
                    genesis_valid = False

                    errors.append(
                        "Genesis record previous hash "
                        "is invalid"
                    )

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                chain_valid = False

                errors.append(
                    "Hash-chain mismatch at sequence "
                    f"{record.sequence_number}"
                )

            if not record.verify_hash():
                hashes_valid = False

                errors.append(
                    "Record hash mismatch at sequence "
                    f"{record.sequence_number}"
                )

            else:
                verified_record_count += 1

            expected_sequence = (
                record.sequence_number
                + 1
            )

            expected_previous_hash = (
                record.record_hash
            )

        if not records:
            warnings.append(
                "Autonomous proposal ledger is empty"
            )

        chain_valid = (
            chain_valid
            and sequence_valid
            and genesis_valid
            and hashes_valid
            and payloads_valid
        )

        first_sequence = (
            records[0].sequence_number
            if records
            else None
        )

        last_sequence = (
            records[-1].sequence_number
            if records
            else None
        )

        return AutonomousProposalAuditReport(
            audit_id=(
                f"autonomous-audit:{uuid4()}"
            ),
            database_path=str(
                self.database_path
            ),
            verified_at=_utc_now_text(),
            record_count=len(
                rows
            ),
            verified_record_count=(
                verified_record_count
            ),
            first_sequence=first_sequence,
            last_sequence=last_sequence,
            chain_valid=chain_valid,
            sequence_valid=sequence_valid,
            hashes_valid=hashes_valid,
            genesis_valid=genesis_valid,
            payloads_valid=payloads_valid,
            errors=tuple(
                dict.fromkeys(
                    errors
                )
            ),
            warnings=tuple(
                dict.fromkeys(
                    warnings
                )
            ),
        )


def verify_autonomous_proposal_store(
    store: AutonomousProposalStore,
) -> AutonomousProposalAuditReport:
    if not isinstance(
        store,
        AutonomousProposalStore,
    ):
        raise TypeError(
            "store must be an "
            "AutonomousProposalStore"
        )

    return AutonomousProposalAuditVerifier(
        store.database_path
    ).verify()
