from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from app.models.noc_wall_dashboard import (
    NOCWallDashboardSnapshot,
)
from app.services.noc_wall_dashboard_validation import (
    NOCWallDashboardValidationResult,
)


STORE_SERVICE_NAME = (
    "SS4TS Immutable NOC Wall Dashboard Store"
)

STORE_SERVICE_VERSION = "1.0.0"

GENESIS_RECORD_HASH = hashlib.sha256(
    b"SS4TS-NOC-WALL-DASHBOARD-GENESIS"
).hexdigest()


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
    value: datetime | None,
) -> datetime:
    resolved = (
        value
        or datetime.now(
            timezone.utc
        )
    )

    if not isinstance(
        resolved,
        datetime,
    ):
        raise TypeError(
            "stored_at must be a datetime"
        )

    if (
        resolved.tzinfo is None
        or resolved.utcoffset() is None
    ):
        raise ValueError(
            "stored_at must be timezone-aware"
        )

    return resolved.astimezone(
        timezone.utc
    )


class NOCWallDashboardStoreError(
    RuntimeError
):
    pass


class NOCWallDashboardDuplicateError(
    NOCWallDashboardStoreError
):
    pass


class NOCWallDashboardIntegrityError(
    NOCWallDashboardStoreError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardRecord:
    sequence_number: int

    dashboard_id: str
    dashboard_fingerprint: str

    generated_at: str
    overall_status: str
    overall_health_score: float
    overall_trend: str

    total_sites: int
    total_devices: int
    total_links: int

    active_incidents: int
    active_predictions: int
    pending_human_approvals: int

    latest_report_id: str | None
    latest_report_fingerprint: str | None

    validation_id: str
    validation_valid: bool
    dashboard_accepted: bool

    snapshot_payload: dict[str, Any]
    validation_payload: dict[str, Any]

    stored_at: str

    previous_record_hash: str
    record_hash: str

    store_name: str
    store_version: str

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
            "dashboard_id":
                self.dashboard_id,
            "dashboard_fingerprint":
                self.dashboard_fingerprint,
            "generated_at":
                self.generated_at,
            "overall_status":
                self.overall_status,
            "overall_health_score":
                self.overall_health_score,
            "overall_trend":
                self.overall_trend,
            "total_sites":
                self.total_sites,
            "total_devices":
                self.total_devices,
            "total_links":
                self.total_links,
            "active_incidents":
                self.active_incidents,
            "active_predictions":
                self.active_predictions,
            "pending_human_approvals":
                self.pending_human_approvals,
            "latest_report_id":
                self.latest_report_id,
            "latest_report_fingerprint":
                self.latest_report_fingerprint,
            "validation_id":
                self.validation_id,
            "validation_valid":
                self.validation_valid,
            "dashboard_accepted":
                self.dashboard_accepted,
            "snapshot_payload":
                self.snapshot_payload,
            "validation_payload":
                self.validation_payload,
            "stored_at":
                self.stored_at,
            "previous_record_hash":
                self.previous_record_hash,
            "store_name":
                self.store_name,
            "store_version":
                self.store_version,
        }

    def calculate_hash(
        self,
    ) -> str:
        return hashlib.sha256(
            _canonical_json(
                self.hash_payload()
            ).encode(
                "utf-8"
            )
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
                "append_only":
                    True,
                "immutable_record":
                    True,
                "read_only_retrieval":
                    True,
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


class NOCWallDashboardStore:
    TABLE_NAME = (
        "noc_wall_dashboard_records"
    )

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(
            database_path
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

        connection.row_factory = (
            sqlite3.Row
        )

        try:
            yield connection
        finally:
            connection.close()

    def _initialize(
        self,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS
                {self.TABLE_NAME} (
                    sequence_number INTEGER
                        PRIMARY KEY AUTOINCREMENT,

                    dashboard_id TEXT
                        NOT NULL UNIQUE,

                    dashboard_fingerprint TEXT
                        NOT NULL UNIQUE,

                    generated_at TEXT
                        NOT NULL,

                    overall_status TEXT
                        NOT NULL,

                    overall_health_score REAL
                        NOT NULL,

                    overall_trend TEXT
                        NOT NULL,

                    total_sites INTEGER
                        NOT NULL,

                    total_devices INTEGER
                        NOT NULL,

                    total_links INTEGER
                        NOT NULL,

                    active_incidents INTEGER
                        NOT NULL,

                    active_predictions INTEGER
                        NOT NULL,

                    pending_human_approvals INTEGER
                        NOT NULL,

                    latest_report_id TEXT,

                    latest_report_fingerprint TEXT,

                    validation_id TEXT
                        NOT NULL UNIQUE,

                    validation_valid INTEGER
                        NOT NULL,

                    dashboard_accepted INTEGER
                        NOT NULL,

                    snapshot_payload TEXT
                        NOT NULL,

                    validation_payload TEXT
                        NOT NULL,

                    stored_at TEXT
                        NOT NULL,

                    previous_record_hash TEXT
                        NOT NULL,

                    record_hash TEXT
                        NOT NULL UNIQUE,

                    store_name TEXT
                        NOT NULL,

                    store_version TEXT
                        NOT NULL
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_{self.TABLE_NAME}_generated_at
                ON {self.TABLE_NAME} (
                    generated_at
                )
                """
            )

            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS
                idx_{self.TABLE_NAME}_status
                ON {self.TABLE_NAME} (
                    overall_status
                )
                """
            )

            connection.commit()

    @staticmethod
    def _row_to_record(
        row: sqlite3.Row,
    ) -> NOCWallDashboardRecord:
        return NOCWallDashboardRecord(
            sequence_number=(
                row["sequence_number"]
            ),
            dashboard_id=(
                row["dashboard_id"]
            ),
            dashboard_fingerprint=(
                row["dashboard_fingerprint"]
            ),
            generated_at=(
                row["generated_at"]
            ),
            overall_status=(
                row["overall_status"]
            ),
            overall_health_score=float(
                row["overall_health_score"]
            ),
            overall_trend=(
                row["overall_trend"]
            ),
            total_sites=(
                row["total_sites"]
            ),
            total_devices=(
                row["total_devices"]
            ),
            total_links=(
                row["total_links"]
            ),
            active_incidents=(
                row["active_incidents"]
            ),
            active_predictions=(
                row["active_predictions"]
            ),
            pending_human_approvals=(
                row[
                    "pending_human_approvals"
                ]
            ),
            latest_report_id=(
                row["latest_report_id"]
            ),
            latest_report_fingerprint=(
                row[
                    "latest_report_fingerprint"
                ]
            ),
            validation_id=(
                row["validation_id"]
            ),
            validation_valid=bool(
                row["validation_valid"]
            ),
            dashboard_accepted=bool(
                row["dashboard_accepted"]
            ),
            snapshot_payload=json.loads(
                row["snapshot_payload"]
            ),
            validation_payload=json.loads(
                row["validation_payload"]
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
            store_name=(
                row["store_name"]
            ),
            store_version=(
                row["store_version"]
            ),
        )

    def count(
        self,
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM {self.TABLE_NAME}
                """
            ).fetchone()

        return int(
            row["count"]
        )

    def _latest_record(
        self,
    ) -> NOCWallDashboardRecord | None:
        with self._connect() as connection:
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
        snapshot: NOCWallDashboardSnapshot,
        validation: (
            NOCWallDashboardValidationResult
        ),
        stored_at: datetime | None = None,
    ) -> NOCWallDashboardRecord:
        if not isinstance(
            snapshot,
            NOCWallDashboardSnapshot,
        ):
            raise TypeError(
                "snapshot must be a "
                "NOCWallDashboardSnapshot"
            )

        if not isinstance(
            validation,
            NOCWallDashboardValidationResult,
        ):
            raise TypeError(
                "validation must be a "
                "NOCWallDashboardValidationResult"
            )

        if not all(
            (
                validation.validation_valid,
                validation.dashboard_accepted,
                validation.dashboard_id
                == snapshot.dashboard_id,
                validation.dashboard_fingerprint
                == snapshot.dashboard_fingerprint,
            )
        ):
            raise NOCWallDashboardIntegrityError(
                "Dashboard validation binding "
                "is invalid"
            )

        resolved_stored_at = (
            _normalize_datetime(
                stored_at
            )
        )

        if (
            resolved_stored_at
            < validation.validated_at
        ):
            raise ValueError(
                "stored_at must not be earlier "
                "than validated_at"
            )

        if (
            validation.validated_at
            < snapshot.generated_at
        ):
            raise ValueError(
                "validated_at must not be earlier "
                "than generated_at"
            )

        latest = self._latest_record()

        sequence_number = (
            latest.sequence_number + 1
            if latest is not None
            else 1
        )

        previous_record_hash = (
            latest.record_hash
            if latest is not None
            else GENESIS_RECORD_HASH
        )

        record_without_hash = (
            NOCWallDashboardRecord(
                sequence_number=(
                    sequence_number
                ),
                dashboard_id=(
                    snapshot.dashboard_id
                ),
                dashboard_fingerprint=(
                    snapshot
                    .dashboard_fingerprint
                ),
                generated_at=(
                    snapshot
                    .generated_at
                    .isoformat()
                ),
                overall_status=(
                    snapshot
                    .overall_status
                    .value
                ),
                overall_health_score=(
                    snapshot
                    .overall_health_score
                ),
                overall_trend=(
                    snapshot
                    .overall_trend
                    .value
                ),
                total_sites=(
                    snapshot.total_sites
                ),
                total_devices=(
                    snapshot.total_devices
                ),
                total_links=(
                    snapshot.total_links
                ),
                active_incidents=(
                    snapshot
                    .active_incidents
                ),
                active_predictions=(
                    snapshot
                    .active_predictions
                ),
                pending_human_approvals=(
                    snapshot
                    .pending_human_approvals
                ),
                latest_report_id=(
                    snapshot
                    .latest_report_id
                ),
                latest_report_fingerprint=(
                    snapshot
                    .latest_report_fingerprint
                ),
                validation_id=(
                    validation.validation_id
                ),
                validation_valid=(
                    validation.validation_valid
                ),
                dashboard_accepted=(
                    validation
                    .dashboard_accepted
                ),
                snapshot_payload=(
                    snapshot.to_dict()
                ),
                validation_payload=(
                    validation.to_dict()
                ),
                stored_at=(
                    resolved_stored_at
                    .isoformat()
                ),
                previous_record_hash=(
                    previous_record_hash
                ),
                record_hash="",
                store_name=(
                    STORE_SERVICE_NAME
                ),
                store_version=(
                    STORE_SERVICE_VERSION
                ),
            )
        )

        record = NOCWallDashboardRecord(
            **{
                **record_without_hash
                .hash_payload(),
                "record_hash":
                    record_without_hash
                    .calculate_hash(),
            }
        )

        try:
            with self._connect() as connection:
                connection.execute(
                    f"""
                    INSERT INTO {self.TABLE_NAME} (
                        sequence_number,
                        dashboard_id,
                        dashboard_fingerprint,
                        generated_at,
                        overall_status,
                        overall_health_score,
                        overall_trend,
                        total_sites,
                        total_devices,
                        total_links,
                        active_incidents,
                        active_predictions,
                        pending_human_approvals,
                        latest_report_id,
                        latest_report_fingerprint,
                        validation_id,
                        validation_valid,
                        dashboard_accepted,
                        snapshot_payload,
                        validation_payload,
                        stored_at,
                        previous_record_hash,
                        record_hash,
                        store_name,
                        store_version
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?
                    )
                    """,
                    (
                        record.sequence_number,
                        record.dashboard_id,
                        record.dashboard_fingerprint,
                        record.generated_at,
                        record.overall_status,
                        record.overall_health_score,
                        record.overall_trend,
                        record.total_sites,
                        record.total_devices,
                        record.total_links,
                        record.active_incidents,
                        record.active_predictions,
                        record.pending_human_approvals,
                        record.latest_report_id,
                        (
                            record
                            .latest_report_fingerprint
                        ),
                        record.validation_id,
                        int(
                            record.validation_valid
                        ),
                        int(
                            record.dashboard_accepted
                        ),
                        _canonical_json(
                            record.snapshot_payload
                        ),
                        _canonical_json(
                            record.validation_payload
                        ),
                        record.stored_at,
                        record.previous_record_hash,
                        record.record_hash,
                        record.store_name,
                        record.store_version,
                    ),
                )

                connection.commit()

        except sqlite3.IntegrityError as exc:
            raise NOCWallDashboardDuplicateError(
                "Dashboard snapshot or validation "
                "already exists"
            ) from exc

        return record

    def get(
        self,
        dashboard_id: str,
    ) -> NOCWallDashboardRecord | None:
        normalized = str(
            dashboard_id
        ).strip()

        if not normalized:
            raise ValueError(
                "dashboard_id must not be empty"
            )

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE dashboard_id = ?
                LIMIT 1
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
        dashboard_fingerprint: str,
    ) -> NOCWallDashboardRecord | None:
        normalized = str(
            dashboard_fingerprint
        ).strip()

        if not normalized:
            raise ValueError(
                "dashboard_fingerprint must not "
                "be empty"
            )

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT *
                FROM {self.TABLE_NAME}
                WHERE dashboard_fingerprint = ?
                LIMIT 1
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
        limit: int = 100,
    ) -> tuple[
        NOCWallDashboardRecord,
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
        ):
            raise TypeError(
                "limit must be an integer"
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
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

            if not all(
                (
                    record.validation_valid,
                    record.dashboard_accepted,
                    record.snapshot_payload.get(
                        "dashboard_id"
                    )
                    == record.dashboard_id,
                    record.snapshot_payload.get(
                        "dashboard_fingerprint"
                    )
                    == record
                    .dashboard_fingerprint,
                    record.validation_payload.get(
                        "validation_id"
                    )
                    == record.validation_id,
                    record.validation_payload.get(
                        "validation_valid"
                    )
                    is True,
                    record.validation_payload.get(
                        "dashboard_accepted"
                    )
                    is True,
                )
            ):
                return False

            expected_sequence += 1
            expected_previous_hash = (
                record.record_hash
            )

        return True
