from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from app.models.executive_predictive_report import (
    ExecutivePredictiveReport,
)
from app.services.executive_predictive_report_validation import (
    ExecutivePredictiveReportValidationResult,
)


GENESIS_RECORD_HASH = "0" * 64

DEFAULT_EXECUTIVE_PREDICTIVE_REPORT_DATABASE = Path(
    os.getenv(
        "SS4TS_EXECUTIVE_PREDICTIVE_REPORT_DB",
        "executive-predictive-reports.db",
    )
)


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _normalize_datetime(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            f"{field_name} must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


class ExecutivePredictiveReportStoreError(
    RuntimeError
):
    pass


class ExecutivePredictiveReportDuplicate(
    ExecutivePredictiveReportStoreError
):
    pass


class ExecutivePredictiveReportIntegrityError(
    ExecutivePredictiveReportStoreError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class ExecutivePredictiveReportRecord:
    sequence_number: int

    report_id: str
    report_fingerprint: str
    report_type: str
    report_title: str

    report_period_start: str
    report_period_end: str
    generated_at: str

    overall_risk_class: str
    overall_health_score: float
    service_outlook: str

    prediction_count: int
    critical_prediction_count: int
    high_risk_prediction_count: int

    source_audit_id: str
    source_audit_valid: bool

    source_prediction_ids: tuple[str, ...]
    source_record_hashes: tuple[str, ...]

    generated_by: str
    schema_version: str

    validation_valid: bool
    validation_payload: dict[str, Any]
    report_payload: dict[str, Any]

    stored_at: str

    previous_record_hash: str
    record_hash: str

    @property
    def report_created(
        self,
    ) -> bool:
        return False

    @property
    def pdf_rendered(
        self,
    ) -> bool:
        return False

    @property
    def incident_created(
        self,
    ) -> bool:
        return False

    @property
    def recommendation_executed(
        self,
    ) -> bool:
        return False

    @property
    def decision_created(
        self,
    ) -> bool:
        return False

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

    def hash_payload(
        self,
    ) -> dict[str, Any]:
        return {
            "sequence_number":
                self.sequence_number,
            "report_id":
                self.report_id,
            "report_fingerprint":
                self.report_fingerprint,
            "report_type":
                self.report_type,
            "report_title":
                self.report_title,
            "report_period_start":
                self.report_period_start,
            "report_period_end":
                self.report_period_end,
            "generated_at":
                self.generated_at,
            "overall_risk_class":
                self.overall_risk_class,
            "overall_health_score":
                self.overall_health_score,
            "service_outlook":
                self.service_outlook,
            "prediction_count":
                self.prediction_count,
            "critical_prediction_count":
                self.critical_prediction_count,
            "high_risk_prediction_count":
                self.high_risk_prediction_count,
            "source_audit_id":
                self.source_audit_id,
            "source_audit_valid":
                self.source_audit_valid,
            "source_prediction_ids":
                list(
                    self.source_prediction_ids
                ),
            "source_record_hashes":
                list(
                    self.source_record_hashes
                ),
            "generated_by":
                self.generated_by,
            "schema_version":
                self.schema_version,
            "validation_valid":
                self.validation_valid,
            "validation_payload":
                self.validation_payload,
            "report_payload":
                self.report_payload,
            "stored_at":
                self.stored_at,
            "previous_record_hash":
                self.previous_record_hash,
        }

    def calculate_hash(
        self,
    ) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.hash_payload()
            ).encode("utf-8")
        ).hexdigest()

    def verify_hash(
        self,
    ) -> bool:
        return (
            self.record_hash
            == self.calculate_hash()
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            **self.hash_payload(),
            "record_hash":
                self.record_hash,
            "report_created":
                False,
            "pdf_rendered":
                False,
            "incident_created":
                False,
            "recommendation_executed":
                False,
            "decision_created":
                False,
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
                "validated_report_only":
                    True,
                "report_created":
                    False,
                "pdf_rendered":
                    False,
                "incident_created":
                    False,
                "recommendation_executed":
                    False,
                "decision_created":
                    False,
                "authorization_created":
                    False,
                "authorization_approved":
                    False,
                "approval_claim_created":
                    False,
                "execution_lease_created":
                    False,
                "execution_allowed":
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


class ExecutivePredictiveReportStore:
    TABLE_NAME = (
        "executive_predictive_report_records"
    )

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_EXECUTIVE_PREDICTIVE_REPORT_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "database_path must not be empty"
            )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    @contextmanager
    def _connect(
        self,
    ) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.database_path
        )

        try:
            connection.row_factory = (
                sqlite3.Row
            )

            connection.execute(
                "PRAGMA journal_mode=WAL"
            )

            connection.execute(
                "PRAGMA foreign_keys=ON"
            )

            yield connection

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def _initialize(
        self,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS
                {self.TABLE_NAME}
                (
                    sequence_number INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    report_id TEXT
                        NOT NULL UNIQUE,

                    report_fingerprint TEXT
                        NOT NULL UNIQUE,

                    report_type TEXT
                        NOT NULL,

                    report_title TEXT
                        NOT NULL,

                    report_period_start TEXT
                        NOT NULL,

                    report_period_end TEXT
                        NOT NULL,

                    generated_at TEXT
                        NOT NULL,

                    overall_risk_class TEXT
                        NOT NULL,

                    overall_health_score REAL
                        NOT NULL,

                    service_outlook TEXT
                        NOT NULL,

                    prediction_count INTEGER
                        NOT NULL,

                    critical_prediction_count INTEGER
                        NOT NULL,

                    high_risk_prediction_count INTEGER
                        NOT NULL,

                    source_audit_id TEXT
                        NOT NULL,

                    source_audit_valid INTEGER
                        NOT NULL,

                    source_prediction_ids TEXT
                        NOT NULL,

                    source_record_hashes TEXT
                        NOT NULL,

                    generated_by TEXT
                        NOT NULL,

                    schema_version TEXT
                        NOT NULL,

                    validation_valid INTEGER
                        NOT NULL,

                    validation_payload TEXT
                        NOT NULL,

                    report_payload TEXT
                        NOT NULL,

                    stored_at TEXT
                        NOT NULL,

                    previous_record_hash TEXT
                        NOT NULL,

                    record_hash TEXT
                        NOT NULL UNIQUE
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_exec_predictive_report_type
                ON {self.TABLE_NAME}
                (
                    report_type
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_exec_predictive_generated_at
                ON {self.TABLE_NAME}
                (
                    generated_at
                )
                """
            )

    @staticmethod
    def _row_to_record(
        row: sqlite3.Row,
    ) -> ExecutivePredictiveReportRecord:
        return ExecutivePredictiveReportRecord(
            sequence_number=(
                int(
                    row["sequence_number"]
                )
            ),
            report_id=(
                row["report_id"]
            ),
            report_fingerprint=(
                row["report_fingerprint"]
            ),
            report_type=(
                row["report_type"]
            ),
            report_title=(
                row["report_title"]
            ),
            report_period_start=(
                row["report_period_start"]
            ),
            report_period_end=(
                row["report_period_end"]
            ),
            generated_at=(
                row["generated_at"]
            ),
            overall_risk_class=(
                row["overall_risk_class"]
            ),
            overall_health_score=(
                float(
                    row[
                        "overall_health_score"
                    ]
                )
            ),
            service_outlook=(
                row["service_outlook"]
            ),
            prediction_count=(
                int(
                    row["prediction_count"]
                )
            ),
            critical_prediction_count=(
                int(
                    row[
                        "critical_prediction_count"
                    ]
                )
            ),
            high_risk_prediction_count=(
                int(
                    row[
                        "high_risk_prediction_count"
                    ]
                )
            ),
            source_audit_id=(
                row["source_audit_id"]
            ),
            source_audit_valid=bool(
                row["source_audit_valid"]
            ),
            source_prediction_ids=tuple(
                json.loads(
                    row[
                        "source_prediction_ids"
                    ]
                )
            ),
            source_record_hashes=tuple(
                json.loads(
                    row[
                        "source_record_hashes"
                    ]
                )
            ),
            generated_by=(
                row["generated_by"]
            ),
            schema_version=(
                row["schema_version"]
            ),
            validation_valid=bool(
                row["validation_valid"]
            ),
            validation_payload=json.loads(
                row["validation_payload"]
            ),
            report_payload=json.loads(
                row["report_payload"]
            ),
            stored_at=(
                row["stored_at"]
            ),
            previous_record_hash=(
                row["previous_record_hash"]
            ),
            record_hash=(
                row["record_hash"]
            ),
        )

    def _latest_record(
        self,
        connection: sqlite3.Connection,
    ) -> ExecutivePredictiveReportRecord | None:
        row = connection.execute(
            f"""
            SELECT *
            FROM {self.TABLE_NAME}
            ORDER BY sequence_number DESC
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return None

        return self._row_to_record(
            row
        )

    def append(
        self,
        *,
        report: ExecutivePredictiveReport,
        validation: (
            ExecutivePredictiveReportValidationResult
        ),
        stored_at: datetime | None = None,
    ) -> ExecutivePredictiveReportRecord:
        if not isinstance(
            report,
            ExecutivePredictiveReport,
        ):
            raise TypeError(
                "report must be an "
                "ExecutivePredictiveReport"
            )

        if not isinstance(
            validation,
            ExecutivePredictiveReportValidationResult,
        ):
            raise TypeError(
                "validation must be an "
                "ExecutivePredictiveReportValidationResult"
            )

        if (
            not validation.validation_valid
            or not validation.report_accepted
        ):
            raise ExecutivePredictiveReportIntegrityError(
                "Only validated and accepted reports "
                "may be stored"
            )

        if (
            validation.report_id
            != report.report_id
        ):
            raise ExecutivePredictiveReportIntegrityError(
                "Validation report_id does not match report"
            )

        if (
            validation.report_fingerprint
            != report.report_fingerprint
        ):
            raise ExecutivePredictiveReportIntegrityError(
                "Validation fingerprint does not match report"
            )

        if (
            report.report_fingerprint
            != report.calculate_fingerprint()
        ):
            raise ExecutivePredictiveReportIntegrityError(
                "Report fingerprint is invalid"
            )

        resolved_stored_at = (
            _normalize_datetime(
                stored_at
                or datetime.now(
                    timezone.utc
                ),
                field_name="stored_at",
            )
        )

        if (
            resolved_stored_at
            < validation.validated_at
        ):
            raise ExecutivePredictiveReportIntegrityError(
                "stored_at must not be earlier "
                "than validated_at"
            )

        report_payload = (
            report.to_dict()
        )

        validation_payload = (
            validation.to_dict()
        )

        with self._connect() as connection:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            duplicate = connection.execute(
                f"""
                SELECT sequence_number
                FROM {self.TABLE_NAME}
                WHERE report_id = ?
                   OR report_fingerprint = ?
                LIMIT 1
                """,
                (
                    report.report_id,
                    report.report_fingerprint,
                ),
            ).fetchone()

            if duplicate is not None:
                raise ExecutivePredictiveReportDuplicate(
                    "Report identity already exists"
                )

            latest = self._latest_record(
                connection
            )

            previous_record_hash = (
                latest.record_hash
                if latest is not None
                else GENESIS_RECORD_HASH
            )

            next_sequence = (
                latest.sequence_number + 1
                if latest is not None
                else 1
            )

            draft = ExecutivePredictiveReportRecord(
                sequence_number=(
                    next_sequence
                ),
                report_id=(
                    report.report_id
                ),
                report_fingerprint=(
                    report.report_fingerprint
                ),
                report_type=(
                    report.report_type.value
                ),
                report_title=(
                    report.report_title
                ),
                report_period_start=(
                    report
                    .report_period_start
                    .isoformat()
                ),
                report_period_end=(
                    report
                    .report_period_end
                    .isoformat()
                ),
                generated_at=(
                    report
                    .generated_at
                    .isoformat()
                ),
                overall_risk_class=(
                    report
                    .overall_risk_class
                    .value
                ),
                overall_health_score=(
                    report.overall_health_score
                ),
                service_outlook=(
                    report.service_outlook.value
                ),
                prediction_count=(
                    report.prediction_count
                ),
                critical_prediction_count=(
                    report
                    .critical_prediction_count
                ),
                high_risk_prediction_count=(
                    report
                    .high_risk_prediction_count
                ),
                source_audit_id=(
                    report.source_audit_id
                ),
                source_audit_valid=(
                    report.source_audit_valid
                ),
                source_prediction_ids=(
                    report.source_prediction_ids
                ),
                source_record_hashes=(
                    report.source_record_hashes
                ),
                generated_by=(
                    report.generated_by
                ),
                schema_version=(
                    report.schema_version
                ),
                validation_valid=(
                    validation.validation_valid
                ),
                validation_payload=(
                    validation_payload
                ),
                report_payload=(
                    report_payload
                ),
                stored_at=(
                    resolved_stored_at
                    .isoformat()
                ),
                previous_record_hash=(
                    previous_record_hash
                ),
                record_hash="",
            )

            record = (
                ExecutivePredictiveReportRecord(
                    sequence_number=(
                        draft.sequence_number
                    ),
                    report_id=(
                        draft.report_id
                    ),
                    report_fingerprint=(
                        draft.report_fingerprint
                    ),
                    report_type=(
                        draft.report_type
                    ),
                    report_title=(
                        draft.report_title
                    ),
                    report_period_start=(
                        draft.report_period_start
                    ),
                    report_period_end=(
                        draft.report_period_end
                    ),
                    generated_at=(
                        draft.generated_at
                    ),
                    overall_risk_class=(
                        draft.overall_risk_class
                    ),
                    overall_health_score=(
                        draft.overall_health_score
                    ),
                    service_outlook=(
                        draft.service_outlook
                    ),
                    prediction_count=(
                        draft.prediction_count
                    ),
                    critical_prediction_count=(
                        draft.critical_prediction_count
                    ),
                    high_risk_prediction_count=(
                        draft.high_risk_prediction_count
                    ),
                    source_audit_id=(
                        draft.source_audit_id
                    ),
                    source_audit_valid=(
                        draft.source_audit_valid
                    ),
                    source_prediction_ids=(
                        draft.source_prediction_ids
                    ),
                    source_record_hashes=(
                        draft.source_record_hashes
                    ),
                    generated_by=(
                        draft.generated_by
                    ),
                    schema_version=(
                        draft.schema_version
                    ),
                    validation_valid=(
                        draft.validation_valid
                    ),
                    validation_payload=(
                        draft.validation_payload
                    ),
                    report_payload=(
                        draft.report_payload
                    ),
                    stored_at=(
                        draft.stored_at
                    ),
                    previous_record_hash=(
                        draft.previous_record_hash
                    ),
                    record_hash=(
                        draft.calculate_hash()
                    ),
                )
            )

            try:
                connection.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME}
                    (
                        sequence_number,
                        report_id,
                        report_fingerprint,
                        report_type,
                        report_title,
                        report_period_start,
                        report_period_end,
                        generated_at,
                        overall_risk_class,
                        overall_health_score,
                        service_outlook,
                        prediction_count,
                        critical_prediction_count,
                        high_risk_prediction_count,
                        source_audit_id,
                        source_audit_valid,
                        source_prediction_ids,
                        source_record_hashes,
                        generated_by,
                        schema_version,
                        validation_valid,
                        validation_payload,
                        report_payload,
                        stored_at,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES
                    (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        record.sequence_number,
                        record.report_id,
                        record.report_fingerprint,
                        record.report_type,
                        record.report_title,
                        record.report_period_start,
                        record.report_period_end,
                        record.generated_at,
                        record.overall_risk_class,
                        record.overall_health_score,
                        record.service_outlook,
                        record.prediction_count,
                        record.critical_prediction_count,
                        record.high_risk_prediction_count,
                        record.source_audit_id,
                        int(
                            record.source_audit_valid
                        ),
                        _canonical_json(
                            list(
                                record.source_prediction_ids
                            )
                        ),
                        _canonical_json(
                            list(
                                record.source_record_hashes
                            )
                        ),
                        record.generated_by,
                        record.schema_version,
                        int(
                            record.validation_valid
                        ),
                        _canonical_json(
                            record.validation_payload
                        ),
                        _canonical_json(
                            record.report_payload
                        ),
                        record.stored_at,
                        record.previous_record_hash,
                        record.record_hash,
                    ),
                )

            except sqlite3.IntegrityError as exc:
                raise ExecutivePredictiveReportDuplicate(
                    "Report identity already exists"
                ) from exc

            stored = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE sequence_number = ?
                """,
                (
                    next_sequence,
                ),
            ).fetchone()

            if stored is None:
                raise ExecutivePredictiveReportStoreError(
                    "Stored report record was not found"
                )

            result = self._row_to_record(
                stored
            )

            if not result.verify_hash():
                raise ExecutivePredictiveReportIntegrityError(
                    "Stored report hash verification failed"
                )

            return result

    def get(
        self,
        report_id: str,
    ) -> ExecutivePredictiveReportRecord | None:
        normalized = str(
            report_id
        ).strip()

        if not normalized:
            raise ValueError(
                "report_id must not be empty"
            )

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE report_id = ?
                """,
                (
                    normalized,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(
            row
        )

    def get_by_fingerprint(
        self,
        report_fingerprint: str,
    ) -> ExecutivePredictiveReportRecord | None:
        normalized = str(
            report_fingerprint
        ).strip().lower()

        if not normalized:
            raise ValueError(
                "report_fingerprint must not be empty"
            )

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE report_fingerprint = ?
                """,
                (
                    normalized,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(
            row
        )

    def list_records(
        self,
        *,
        limit: int = 1000,
    ) -> tuple[
        ExecutivePredictiveReportRecord,
        ...,
    ]:
        if (
            isinstance(
                limit,
                bool,
            )
            or not isinstance(
                limit,
                int,
            )
            or limit <= 0
        ):
            raise ValueError(
                "limit must be a positive integer"
            )

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                ORDER BY sequence_number ASC
                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()

        return tuple(
            self._row_to_record(
                row
            )
            for row in rows
        )

    def count(
        self,
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM {self.TABLE_NAME}
                """
            ).fetchone()

        return int(
            row["total"]
        )

    def verify_chain(
        self,
    ) -> bool:
        records = self.list_records(
            limit=1_000_000
        )

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        for record in records:
            if (
                record.sequence_number
                != expected_sequence
            ):
                return False

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                return False

            if not record.verify_hash():
                return False

            expected_sequence += 1
            expected_previous_hash = (
                record.record_hash
            )

        return True
