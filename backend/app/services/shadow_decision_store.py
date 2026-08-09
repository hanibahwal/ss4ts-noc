from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.models.shadow_decision import (
    ShadowDecisionRecord,
)


DEFAULT_SHADOW_DATABASE = Path(
    "/var/lib/ss4ts-noc/shadow-decisions.db"
)


class ShadowDecisionStore:
    """
    Local persistence for autonomous shadow-mode decisions.

    This store performs local SQLite I/O only.
    It never contacts managed devices and never
    executes device or network commands.
    """

    def __init__(
        self,
        database_path: str | Path = DEFAULT_SHADOW_DATABASE,
    ) -> None:
        self.database_path = Path(database_path)

        if not str(self.database_path).strip():
            raise ValueError(
                "Shadow database path must not be empty"
            )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    @contextmanager
    def _connect(
        self,
    ) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.database_path
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute(
                "PRAGMA journal_mode = WAL"
            )
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                shadow_decisions (
                    shadow_id TEXT PRIMARY KEY,
                    decision_id TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,
                    proposed_action TEXT NOT NULL,
                    confidence_percent REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    predicted_outcome TEXT NOT NULL,
                    simulation_status TEXT NOT NULL,
                    dry_run_only INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_shadow_decision_created
                ON shadow_decisions (
                    created_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_shadow_decision_source
                ON shadow_decisions (
                    source_node_id,
                    created_at DESC
                )
                """
            )

    @staticmethod
    def _from_row(
        row: sqlite3.Row,
    ) -> ShadowDecisionRecord:
        return ShadowDecisionRecord(
            shadow_id=row["shadow_id"],
            decision_id=row["decision_id"],
            source_node_id=row["source_node_id"],
            proposed_action=row["proposed_action"],
            confidence_percent=float(
                row["confidence_percent"]
            ),
            risk_level=row["risk_level"],
            predicted_outcome=json.loads(
                row["predicted_outcome"]
            ),
            simulation_status=row["simulation_status"],
            dry_run_only=bool(
                row["dry_run_only"]
            ),
            created_at=datetime.fromisoformat(
                row["created_at"]
            ),
            metadata=json.loads(
                row["metadata"]
            ),
        )

    def create(
        self,
        record: ShadowDecisionRecord,
    ) -> ShadowDecisionRecord:
        if not isinstance(
            record,
            ShadowDecisionRecord,
        ):
            raise TypeError(
                "record must be a ShadowDecisionRecord"
            )

        with self._connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO shadow_decisions (
                        shadow_id,
                        decision_id,
                        source_node_id,
                        proposed_action,
                        confidence_percent,
                        risk_level,
                        predicted_outcome,
                        simulation_status,
                        dry_run_only,
                        created_at,
                        metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.shadow_id,
                        record.decision_id,
                        record.source_node_id,
                        record.proposed_action,
                        record.confidence_percent,
                        record.risk_level,
                        json.dumps(
                            record.predicted_outcome,
                            sort_keys=True,
                            default=str,
                        ),
                        record.simulation_status,
                        int(record.dry_run_only),
                        record.created_at.isoformat(),
                        json.dumps(
                            record.metadata,
                            sort_keys=True,
                            default=str,
                        ),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    "Shadow decision already exists"
                ) from exc

        return record

    def get(
        self,
        shadow_id: str,
    ) -> ShadowDecisionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM shadow_decisions
                WHERE shadow_id = ?
                """,
                (shadow_id,),
            ).fetchone()

        if row is None:
            return None

        return self._from_row(row)

    def list_recent(
        self,
        *,
        limit: int = 100,
    ) -> list[ShadowDecisionRecord]:
        if not 1 <= limit <= 1000:
            raise ValueError(
                "limit must be between 1 and 1000"
            )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM shadow_decisions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            self._from_row(row)
            for row in rows
        ]
