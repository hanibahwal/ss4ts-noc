from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from app.services.data_directory import data_path
import sqlite3
from typing import Any

from app.models.predictive_intelligence import (
    PredictiveIntelligence,
)
from app.services.predictive_intelligence_validation import (
    PredictiveIntelligenceValidationResult,
)


GENESIS_RECORD_HASH = "0" * 64

DEFAULT_DATABASE_NAME = (
    "predictive-intelligence.db"
)

DATABASE_ENVIRONMENT_VARIABLE = (
    "SS4TS_PREDICTIVE_INTELLIGENCE_DB"
)


class PredictiveIntelligenceStoreError(
    RuntimeError
):
    pass


class PredictiveIntelligenceDuplicate(
    PredictiveIntelligenceStoreError
):
    pass


class PredictiveIntelligenceIntegrityError(
    PredictiveIntelligenceStoreError
):
    pass


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


def _parse_datetime(
    value: Any,
    *,
    field_name: str,
) -> datetime:
    try:
        parsed = datetime.fromisoformat(
            str(
                value
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise PredictiveIntelligenceIntegrityError(
            f"{field_name} is invalid"
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise PredictiveIntelligenceIntegrityError(
            f"{field_name} must be timezone-aware"
        )

    return parsed.astimezone(
        timezone.utc
    )


def _normalize_stored_at(
    stored_at: datetime | None,
) -> datetime:
    value = (
        stored_at
        or datetime.now(
            timezone.utc
        )
    )

    if not isinstance(
        value,
        datetime,
    ):
        raise TypeError(
            "stored_at must be a datetime"
        )

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            "stored_at must be timezone-aware"
        )

    return value.astimezone(
        timezone.utc
    )


@dataclass(
    frozen=True,
    slots=True,
)
class PredictiveIntelligenceRecord:
    sequence_number: int

    prediction_id: str
    prediction_fingerprint: str

    prediction_type: str
    subject_type: str
    subject_id: str

    observed_at: str
    prediction_window_start: str
    prediction_window_end: str

    current_state: str
    predicted_state: str

    current_value: float | None
    predicted_value: float | None
    unit: str | None

    confidence_percent: float
    probability_percent: float
    risk_class: str
    severity: str

    evidence: tuple[str, ...]
    contributing_factors: tuple[str, ...]
    source_metric_ids: tuple[str, ...]

    model_name: str
    model_version: str
    metadata: dict[str, Any]

    created_at: str
    stored_at: str

    validation_valid: bool
    validation_payload: dict[str, Any]
    prediction_payload: dict[str, Any]

    previous_record_hash: str
    record_hash: str

    @property
    def incident_created(
        self,
    ) -> bool:
        return False

    @property
    def recommendation_created(
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
    def approval_claim_created(
        self,
    ) -> bool:
        return False

    @property
    def execution_lease_created(
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
            "prediction_id":
                self.prediction_id,
            "prediction_fingerprint":
                self.prediction_fingerprint,
            "prediction_type":
                self.prediction_type,
            "subject_type":
                self.subject_type,
            "subject_id":
                self.subject_id,
            "observed_at":
                self.observed_at,
            "prediction_window_start":
                self.prediction_window_start,
            "prediction_window_end":
                self.prediction_window_end,
            "current_state":
                self.current_state,
            "predicted_state":
                self.predicted_state,
            "current_value":
                self.current_value,
            "predicted_value":
                self.predicted_value,
            "unit":
                self.unit,
            "confidence_percent":
                self.confidence_percent,
            "probability_percent":
                self.probability_percent,
            "risk_class":
                self.risk_class,
            "severity":
                self.severity,
            "evidence":
                list(
                    self.evidence
                ),
            "contributing_factors":
                list(
                    self.contributing_factors
                ),
            "source_metric_ids":
                list(
                    self.source_metric_ids
                ),
            "model_name":
                self.model_name,
            "model_version":
                self.model_version,
            "metadata":
                self.metadata,
            "created_at":
                self.created_at,
            "stored_at":
                self.stored_at,
            "validation_valid":
                self.validation_valid,
            "validation_payload":
                self.validation_payload,
            "prediction_payload":
                self.prediction_payload,
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
            "incident_created":
                False,
            "recommendation_created":
                False,
            "decision_created":
                False,
            "authorization_created":
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
                "immutable_predictive_store":
                    True,
                "append_only":
                    True,
                "read_only_record":
                    True,
                "incident_created":
                    False,
                "recommendation_created":
                    False,
                "decision_created":
                    False,
                "authorization_created":
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


class PredictiveIntelligenceStore:
    TABLE_NAME = (
        "predictive_intelligence_records"
    )

    def __init__(
        self,
        database_path: (
            str
            | os.PathLike[str]
            | None
        ) = None,
    ) -> None:
        configured_path = (
            database_path
            or os.getenv(
                DATABASE_ENVIRONMENT_VARIABLE
            )
            or data_path(
                DEFAULT_DATABASE_NAME
            )
        )

        self.database_path = Path(
            configured_path
        )

        parent = self.database_path.parent

        if (
            str(parent)
            not in {
                "",
                ".",
            }
        ):
            parent.mkdir(
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
            "PRAGMA journal_mode=WAL"
        )

        connection.execute(
            "PRAGMA synchronous=FULL"
        )

        connection.execute(
            "PRAGMA foreign_keys=ON"
        )

        return connection

    def initialize(
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

                    prediction_id TEXT
                        NOT NULL UNIQUE,

                    prediction_fingerprint TEXT
                        NOT NULL UNIQUE,

                    prediction_type TEXT
                        NOT NULL,

                    subject_type TEXT
                        NOT NULL,

                    subject_id TEXT
                        NOT NULL,

                    observed_at TEXT
                        NOT NULL,

                    prediction_window_start TEXT
                        NOT NULL,

                    prediction_window_end TEXT
                        NOT NULL,

                    current_state TEXT
                        NOT NULL,

                    predicted_state TEXT
                        NOT NULL,

                    current_value REAL,

                    predicted_value REAL,

                    unit TEXT,

                    confidence_percent REAL
                        NOT NULL,

                    probability_percent REAL
                        NOT NULL,

                    risk_class TEXT
                        NOT NULL,

                    severity TEXT
                        NOT NULL,

                    evidence TEXT
                        NOT NULL,

                    contributing_factors TEXT
                        NOT NULL,

                    source_metric_ids TEXT
                        NOT NULL,

                    model_name TEXT
                        NOT NULL,

                    model_version TEXT
                        NOT NULL,

                    metadata TEXT
                        NOT NULL,

                    created_at TEXT
                        NOT NULL,

                    stored_at TEXT
                        NOT NULL,

                    validation_valid INTEGER
                        NOT NULL,

                    validation_payload TEXT
                        NOT NULL,

                    prediction_payload TEXT
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
                idx_predictive_subject
                ON {self.TABLE_NAME}
                (
                    subject_type,
                    subject_id
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_predictive_type
                ON {self.TABLE_NAME}
                (
                    prediction_type
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_predictive_created_at
                ON {self.TABLE_NAME}
                (
                    created_at
                )
                """
            )

            connection.commit()

    @staticmethod
    def _validate_prediction(
        prediction: PredictiveIntelligence,
        validation: (
            PredictiveIntelligenceValidationResult
        ),
    ) -> None:
        if not isinstance(
            prediction,
            PredictiveIntelligence,
        ):
            raise TypeError(
                "prediction must be a "
                "PredictiveIntelligence"
            )

        if not isinstance(
            validation,
            PredictiveIntelligenceValidationResult,
        ):
            raise TypeError(
                "validation must be a "
                "PredictiveIntelligenceValidationResult"
            )

        if (
            validation.prediction_id
            != prediction.prediction_id
        ):
            raise PredictiveIntelligenceIntegrityError(
                "Validation prediction_id does not "
                "match prediction"
            )

        if not validation.validation_valid:
            raise PredictiveIntelligenceIntegrityError(
                "Prediction validation is not valid"
            )

        if not validation.prediction_accepted:
            raise PredictiveIntelligenceIntegrityError(
                "Prediction was not accepted"
            )

        calculated_fingerprint = (
            prediction.calculate_fingerprint()
        )

        if (
            prediction.prediction_fingerprint
            != calculated_fingerprint
        ):
            raise PredictiveIntelligenceIntegrityError(
                "Prediction fingerprint is invalid"
            )

        if (
            validation.incident_created
            or validation.recommendation_created
            or validation.decision_created
            or validation.authorization_created
            or validation.approval_claim_created
            or validation.execution_lease_created
            or validation.execution_allowed
            or validation.can_execute
        ):
            raise PredictiveIntelligenceIntegrityError(
                "Validation contains unsafe execution claims"
            )

        if (
            prediction.incident_created
            or prediction.recommendation_created
            or prediction.decision_created
            or prediction.authorization_created
            or prediction.approval_claim_created
            or prediction.execution_lease_created
            or prediction.execution_allowed
            or prediction.can_execute
        ):
            raise PredictiveIntelligenceIntegrityError(
                "Prediction contains unsafe execution claims"
            )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> PredictiveIntelligenceRecord:
        return PredictiveIntelligenceRecord(
            sequence_number=int(
                row["sequence_number"]
            ),
            prediction_id=str(
                row["prediction_id"]
            ),
            prediction_fingerprint=str(
                row["prediction_fingerprint"]
            ),
            prediction_type=str(
                row["prediction_type"]
            ),
            subject_type=str(
                row["subject_type"]
            ),
            subject_id=str(
                row["subject_id"]
            ),
            observed_at=str(
                row["observed_at"]
            ),
            prediction_window_start=str(
                row[
                    "prediction_window_start"
                ]
            ),
            prediction_window_end=str(
                row[
                    "prediction_window_end"
                ]
            ),
            current_state=str(
                row["current_state"]
            ),
            predicted_state=str(
                row["predicted_state"]
            ),
            current_value=(
                float(
                    row["current_value"]
                )
                if row["current_value"]
                is not None
                else None
            ),
            predicted_value=(
                float(
                    row["predicted_value"]
                )
                if row["predicted_value"]
                is not None
                else None
            ),
            unit=(
                str(
                    row["unit"]
                )
                if row["unit"]
                is not None
                else None
            ),
            confidence_percent=float(
                row["confidence_percent"]
            ),
            probability_percent=float(
                row["probability_percent"]
            ),
            risk_class=str(
                row["risk_class"]
            ),
            severity=str(
                row["severity"]
            ),
            evidence=tuple(
                json.loads(
                    row["evidence"]
                )
            ),
            contributing_factors=tuple(
                json.loads(
                    row[
                        "contributing_factors"
                    ]
                )
            ),
            source_metric_ids=tuple(
                json.loads(
                    row["source_metric_ids"]
                )
            ),
            model_name=str(
                row["model_name"]
            ),
            model_version=str(
                row["model_version"]
            ),
            metadata=dict(
                json.loads(
                    row["metadata"]
                )
            ),
            created_at=str(
                row["created_at"]
            ),
            stored_at=str(
                row["stored_at"]
            ),
            validation_valid=bool(
                row["validation_valid"]
            ),
            validation_payload=dict(
                json.loads(
                    row["validation_payload"]
                )
            ),
            prediction_payload=dict(
                json.loads(
                    row["prediction_payload"]
                )
            ),
            previous_record_hash=str(
                row["previous_record_hash"]
            ),
            record_hash=str(
                row["record_hash"]
            ),
        )

    def _latest_record_hash(
        self,
        connection: sqlite3.Connection,
    ) -> str:
        row = connection.execute(
            f"""
            SELECT record_hash
            FROM {self.TABLE_NAME}
            ORDER BY sequence_number DESC
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return GENESIS_RECORD_HASH

        return str(
            row["record_hash"]
        )

    def append(
        self,
        *,
        prediction: PredictiveIntelligence,
        validation: (
            PredictiveIntelligenceValidationResult
        ),
        stored_at: datetime | None = None,
    ) -> PredictiveIntelligenceRecord:
        self._validate_prediction(
            prediction,
            validation,
        )

        resolved_stored_at = (
            _normalize_stored_at(
                stored_at
            )
        )

        if (
            resolved_stored_at
            < prediction.created_at
        ):
            raise PredictiveIntelligenceIntegrityError(
                "stored_at must not be earlier "
                "than prediction created_at"
            )

        prediction_payload = (
            prediction.to_dict()
        )

        validation_payload = (
            validation.to_dict()
        )

        with self._connect() as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                previous_record_hash = (
                    self._latest_record_hash(
                        connection
                    )
                )

                next_sequence_row = (
                    connection.execute(
                        f"""
                        SELECT
                            COALESCE(
                                MAX(sequence_number),
                                0
                            ) + 1
                            AS next_sequence
                        FROM {self.TABLE_NAME}
                        """
                    ).fetchone()
                )

                next_sequence = int(
                    next_sequence_row[
                        "next_sequence"
                    ]
                )

                provisional_record = (
                    PredictiveIntelligenceRecord(
                        sequence_number=(
                            next_sequence
                        ),
                        prediction_id=(
                            prediction.prediction_id
                        ),
                        prediction_fingerprint=(
                            prediction
                            .prediction_fingerprint
                        ),
                        prediction_type=(
                            prediction
                            .prediction_type
                            .value
                        ),
                        subject_type=(
                            prediction
                            .subject_type
                            .value
                        ),
                        subject_id=(
                            prediction.subject_id
                        ),
                        observed_at=(
                            prediction
                            .observed_at
                            .isoformat()
                        ),
                        prediction_window_start=(
                            prediction
                            .prediction_window_start
                            .isoformat()
                        ),
                        prediction_window_end=(
                            prediction
                            .prediction_window_end
                            .isoformat()
                        ),
                        current_state=(
                            prediction
                            .current_state
                            .value
                        ),
                        predicted_state=(
                            prediction
                            .predicted_state
                            .value
                        ),
                        current_value=(
                            prediction.current_value
                        ),
                        predicted_value=(
                            prediction.predicted_value
                        ),
                        unit=(
                            prediction.unit
                        ),
                        confidence_percent=(
                            prediction
                            .confidence_percent
                        ),
                        probability_percent=(
                            prediction
                            .probability_percent
                        ),
                        risk_class=(
                            prediction
                            .risk_class
                            .value
                        ),
                        severity=(
                            prediction
                            .severity
                            .value
                        ),
                        evidence=(
                            prediction.evidence
                        ),
                        contributing_factors=(
                            prediction
                            .contributing_factors
                        ),
                        source_metric_ids=(
                            prediction
                            .source_metric_ids
                        ),
                        model_name=(
                            prediction.model_name
                        ),
                        model_version=(
                            prediction.model_version
                        ),
                        metadata=dict(
                            prediction.metadata
                        ),
                        created_at=(
                            prediction
                            .created_at
                            .isoformat()
                        ),
                        stored_at=(
                            resolved_stored_at
                            .isoformat()
                        ),
                        validation_valid=(
                            validation
                            .validation_valid
                        ),
                        validation_payload=(
                            validation_payload
                        ),
                        prediction_payload=(
                            prediction_payload
                        ),
                        previous_record_hash=(
                            previous_record_hash
                        ),
                        record_hash="",
                    )
                )

                record_hash = (
                    provisional_record
                    .calculate_hash()
                )

                connection.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME}
                    (
                        sequence_number,
                        prediction_id,
                        prediction_fingerprint,
                        prediction_type,
                        subject_type,
                        subject_id,
                        observed_at,
                        prediction_window_start,
                        prediction_window_end,
                        current_state,
                        predicted_state,
                        current_value,
                        predicted_value,
                        unit,
                        confidence_percent,
                        probability_percent,
                        risk_class,
                        severity,
                        evidence,
                        contributing_factors,
                        source_metric_ids,
                        model_name,
                        model_version,
                        metadata,
                        created_at,
                        stored_at,
                        validation_valid,
                        validation_payload,
                        prediction_payload,
                        previous_record_hash,
                        record_hash
                    )
                    VALUES
                    (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?
                    )
                    """,
                    (
                        provisional_record
                        .sequence_number,
                        provisional_record
                        .prediction_id,
                        provisional_record
                        .prediction_fingerprint,
                        provisional_record
                        .prediction_type,
                        provisional_record
                        .subject_type,
                        provisional_record
                        .subject_id,
                        provisional_record
                        .observed_at,
                        provisional_record
                        .prediction_window_start,
                        provisional_record
                        .prediction_window_end,
                        provisional_record
                        .current_state,
                        provisional_record
                        .predicted_state,
                        provisional_record
                        .current_value,
                        provisional_record
                        .predicted_value,
                        provisional_record
                        .unit,
                        provisional_record
                        .confidence_percent,
                        provisional_record
                        .probability_percent,
                        provisional_record
                        .risk_class,
                        provisional_record
                        .severity,
                        _canonical_json(
                            provisional_record
                            .evidence
                        ),
                        _canonical_json(
                            provisional_record
                            .contributing_factors
                        ),
                        _canonical_json(
                            provisional_record
                            .source_metric_ids
                        ),
                        provisional_record
                        .model_name,
                        provisional_record
                        .model_version,
                        _canonical_json(
                            provisional_record
                            .metadata
                        ),
                        provisional_record
                        .created_at,
                        provisional_record
                        .stored_at,
                        int(
                            provisional_record
                            .validation_valid
                        ),
                        _canonical_json(
                            provisional_record
                            .validation_payload
                        ),
                        _canonical_json(
                            provisional_record
                            .prediction_payload
                        ),
                        provisional_record
                        .previous_record_hash,
                        record_hash,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as exc:
                connection.rollback()

                message = str(
                    exc
                ).lower()

                if (
                    "unique"
                    in message
                    or "prediction_id"
                    in message
                    or "prediction_fingerprint"
                    in message
                ):
                    raise PredictiveIntelligenceDuplicate(
                        "Predictive intelligence record "
                        "already exists"
                    ) from exc

                raise PredictiveIntelligenceStoreError(
                    "Failed to append predictive "
                    "intelligence record"
                ) from exc

            except Exception:
                connection.rollback()
                raise

        record = self.get(
            prediction.prediction_id
        )

        if record is None:
            raise PredictiveIntelligenceStoreError(
                "Stored prediction could not be retrieved"
            )

        if not record.verify_hash():
            raise PredictiveIntelligenceIntegrityError(
                "Stored prediction record hash is invalid"
            )

        return record

    def get(
        self,
        prediction_id: str,
    ) -> PredictiveIntelligenceRecord | None:
        normalized_id = str(
            prediction_id
        ).strip()

        if not normalized_id:
            raise ValueError(
                "prediction_id must not be empty"
            )

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE prediction_id = ?
                LIMIT 1
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

    def get_by_fingerprint(
        self,
        prediction_fingerprint: str,
    ) -> PredictiveIntelligenceRecord | None:
        normalized = str(
            prediction_fingerprint
        ).strip().lower()

        if not normalized:
            raise ValueError(
                "prediction_fingerprint must not "
                "be empty"
            )

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE prediction_fingerprint = ?
                LIMIT 1
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
        offset: int = 0,
    ) -> tuple[
        PredictiveIntelligenceRecord,
        ...,
    ]:
        if (
            not isinstance(
                limit,
                int,
            )
            or limit <= 0
        ):
            raise ValueError(
                "limit must be a positive integer"
            )

        if (
            not isinstance(
                offset,
                int,
            )
            or offset < 0
        ):
            raise ValueError(
                "offset must be a non-negative integer"
            )

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                ORDER BY sequence_number ASC
                LIMIT ? OFFSET ?
                """,
                (
                    limit,
                    offset,
                ),
            ).fetchall()

        return tuple(
            self._record_from_row(
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
                SELECT COUNT(*) AS record_count
                FROM {self.TABLE_NAME}
                """
            ).fetchone()

        return int(
            row["record_count"]
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
