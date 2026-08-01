from __future__ import annotations

import hashlib
import json
import sqlite3

from contextlib import closing
from dataclasses import replace
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any

from app.models.execution_concurrency import (
    AuthorizationMutationAction,
    AuthorizationMutationResult,
    AuthorizationMutationToken,
    AuthorizationVersionConflict,
    IdempotencyConflict,
    IdempotencyDisposition,
)
from app.models.execution_authorization import (
    ApprovalIdentity,
    ApprovalRole,
    AuthorizationDecision,
    AuthorizationStatus,
    ExecutionAuthorization,
    ExecutionRiskClass,
)


DEFAULT_AUTHORIZATION_DATABASE = Path(
    "/var/lib/ss4ts-noc/"
    "execution-authorization.db"
)


ROLE_PRIORITY = {
    ApprovalRole.REQUESTER: 0,
    ApprovalRole.NETWORK_ENGINEER: 10,
    ApprovalRole.SENIOR_ENGINEER: 20,
    ApprovalRole.CHANGE_MANAGER: 30,
    ApprovalRole.ADMINISTRATOR: 40,
    ApprovalRole.UNKNOWN: -1,
}


def canonical_authorization_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _identity_payload(
    identity: ApprovalIdentity | None,
) -> dict[str, Any] | None:
    if identity is None:
        return None

    return identity.to_dict()


def _authorization_payload(
    authorization: ExecutionAuthorization,
) -> dict[str, Any]:
    """
    Return stable authorization content.

    Derived properties such as is_expired and is_usable are excluded
    because they can change as time passes.
    """

    return {
        "authorization_id":
            authorization.authorization_id,
        "plan_id":
            authorization.plan_id,
        "decision_id":
            authorization.decision_id,
        "source_node_id":
            authorization.source_node_id,
        "requester":
            authorization.requester.to_dict(),
        "approver":
            _identity_payload(
                authorization.approver
            ),
        "risk_class":
            authorization.risk_class.value,
        "status":
            authorization.status.value,
        "decision":
            authorization.decision.value,
        "requested_at":
            authorization.requested_at.isoformat(),
        "approved_at": (
            authorization.approved_at.isoformat()
            if authorization.approved_at
            else None
        ),
        "expires_at": (
            authorization.expires_at.isoformat()
            if authorization.expires_at
            else None
        ),
        "rejection_reason":
            authorization.rejection_reason,
        "revocation_reason":
            authorization.revocation_reason,
        "dry_run_required":
            authorization.dry_run_required,
        "rollback_required":
            authorization.rollback_required,
        "verification_required":
            authorization.verification_required,
        "execution_allowed":
            authorization.execution_allowed,
        "one_time_use":
            authorization.one_time_use,
        "consumed":
            authorization.consumed,
        "confidence_percent":
            authorization.confidence_percent,
        "policy_reasons":
            list(
                authorization.policy_reasons
            ),
        "metadata":
            dict(authorization.metadata),
    }


def calculate_authorization_checksum(
    authorization: ExecutionAuthorization,
) -> str:
    content = canonical_authorization_json(
        _authorization_payload(
            authorization
        )
    )

    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    parsed = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


def _identity_from_payload(
    payload: dict[str, Any] | None,
) -> ApprovalIdentity | None:
    if payload is None:
        return None

    return ApprovalIdentity(
        identity_id=str(
            payload.get(
                "identity_id",
                "",
            )
        ),
        display_name=str(
            payload.get(
                "display_name",
                "",
            )
        ),
        role=ApprovalRole(
            payload.get(
                "role",
                ApprovalRole.UNKNOWN.value,
            )
        ),
        email=payload.get("email"),
        metadata=payload.get(
            "metadata",
            {},
        ),
    )


class ExecutionAuthorizationStore:
    """
    Persist execution authorizations and lifecycle events in SQLite.

    This store performs local database I/O only. It never contacts
    managed devices and never executes network commands.
    """

    def __init__(
        self,
        database_path: str | Path = (
            DEFAULT_AUTHORIZATION_DATABASE
        ),
    ) -> None:
        self.database_path = Path(
            database_path
        )

        if not str(
            self.database_path
        ).strip():
            raise ValueError(
                "Authorization database path "
                "must not be empty"
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
            self.database_path
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
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
                execution_authorizations (
                    authorization_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,

                    requester_payload TEXT NOT NULL,
                    approver_payload TEXT,

                    risk_class TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT NOT NULL,

                    requested_at TEXT NOT NULL,
                    approved_at TEXT,
                    expires_at TEXT,

                    rejection_reason TEXT,
                    revocation_reason TEXT,

                    dry_run_required INTEGER NOT NULL,
                    rollback_required INTEGER NOT NULL,
                    verification_required INTEGER NOT NULL,
                    execution_allowed INTEGER NOT NULL,
                    one_time_use INTEGER NOT NULL,
                    consumed INTEGER NOT NULL,

                    confidence_percent REAL NOT NULL,
                    policy_reasons TEXT NOT NULL,
                    metadata TEXT NOT NULL,

                    checksum TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            authorization_columns = {
                row["name"]
                for row in connection.execute(
                    """
                    PRAGMA table_info(
                        execution_authorizations
                    )
                    """
                ).fetchall()
            }

            if (
                "record_version"
                not in authorization_columns
            ):
                connection.execute(
                    """
                    ALTER TABLE
                    execution_authorizations
                    ADD COLUMN
                    record_version INTEGER
                    NOT NULL DEFAULT 1
                    """
                )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_authorization_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    authorization_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,

                    previous_version INTEGER NOT NULL,
                    current_version INTEGER NOT NULL,

                    response_payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,

                    FOREIGN KEY (
                        authorization_id
                    )
                    REFERENCES execution_authorizations (
                        authorization_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_authorization_idempotency
                ON execution_authorization_idempotency (
                    authorization_id,
                    action,
                    created_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_authorization_status
                ON execution_authorizations (
                    status,
                    requested_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_authorization_source
                ON execution_authorizations (
                    source_node_id,
                    requested_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_authorization_plan
                ON execution_authorizations (
                    plan_id
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS
                execution_authorization_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    authorization_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_at TEXT NOT NULL,
                    actor_payload TEXT,
                    details_payload TEXT NOT NULL,

                    FOREIGN KEY (
                        authorization_id
                    )
                    REFERENCES execution_authorizations (
                        authorization_id
                    )
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_execution_authorization_events
                ON execution_authorization_events (
                    authorization_id,
                    event_at ASC
                )
                """
            )

            connection.commit()

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> ExecutionAuthorization:
        requester_payload = json.loads(
            row["requester_payload"]
        )

        approver_payload = (
            json.loads(
                row["approver_payload"]
            )
            if row["approver_payload"]
            else None
        )

        return ExecutionAuthorization(
            authorization_id=
                row["authorization_id"],
            plan_id=row["plan_id"],
            decision_id=row["decision_id"],
            source_node_id=
                row["source_node_id"],
            requester=_identity_from_payload(
                requester_payload
            ),
            approver=_identity_from_payload(
                approver_payload
            ),
            risk_class=ExecutionRiskClass(
                row["risk_class"]
            ),
            status=AuthorizationStatus(
                row["status"]
            ),
            decision=AuthorizationDecision(
                row["decision"]
            ),
            requested_at=_parse_datetime(
                row["requested_at"]
            ),
            approved_at=_parse_datetime(
                row["approved_at"]
            ),
            expires_at=_parse_datetime(
                row["expires_at"]
            ),
            rejection_reason=
                row["rejection_reason"],
            revocation_reason=
                row["revocation_reason"],
            dry_run_required=bool(
                row["dry_run_required"]
            ),
            rollback_required=bool(
                row["rollback_required"]
            ),
            verification_required=bool(
                row[
                    "verification_required"
                ]
            ),
            execution_allowed=bool(
                row["execution_allowed"]
            ),
            one_time_use=bool(
                row["one_time_use"]
            ),
            consumed=bool(
                row["consumed"]
            ),
            confidence_percent=float(
                row["confidence_percent"]
            ),
            policy_reasons=json.loads(
                row["policy_reasons"]
            ),
            metadata=json.loads(
                row["metadata"]
            ),
        )

    def _write(
        self,
        authorization: ExecutionAuthorization,
        *,
        insert: bool,
    ) -> None:
        checksum = (
            calculate_authorization_checksum(
                authorization
            )
        )

        updated_at = datetime.now(
            timezone.utc
        ).isoformat()

        values = (
            authorization.authorization_id,
            authorization.plan_id,
            authorization.decision_id,
            authorization.source_node_id,
            canonical_authorization_json(
                authorization.requester
                .to_dict()
            ),
            (
                canonical_authorization_json(
                    authorization.approver
                    .to_dict()
                )
                if authorization.approver
                else None
            ),
            authorization.risk_class.value,
            authorization.status.value,
            authorization.decision.value,
            authorization.requested_at
            .isoformat(),
            (
                authorization.approved_at
                .isoformat()
                if authorization.approved_at
                else None
            ),
            (
                authorization.expires_at
                .isoformat()
                if authorization.expires_at
                else None
            ),
            authorization.rejection_reason,
            authorization.revocation_reason,
            int(
                authorization.dry_run_required
            ),
            int(
                authorization.rollback_required
            ),
            int(
                authorization
                .verification_required
            ),
            int(
                authorization.execution_allowed
            ),
            int(
                authorization.one_time_use
            ),
            int(
                authorization.consumed
            ),
            authorization.confidence_percent,
            canonical_authorization_json(
                authorization.policy_reasons
            ),
            canonical_authorization_json(
                authorization.metadata
            ),
            checksum,
            updated_at,
        )

        with closing(
            self._connect()
        ) as connection:
            if insert:
                try:
                    connection.execute(
                        """
                        INSERT INTO
                        execution_authorizations (
                            authorization_id,
                            plan_id,
                            decision_id,
                            source_node_id,
                            requester_payload,
                            approver_payload,
                            risk_class,
                            status,
                            decision,
                            requested_at,
                            approved_at,
                            expires_at,
                            rejection_reason,
                            revocation_reason,
                            dry_run_required,
                            rollback_required,
                            verification_required,
                            execution_allowed,
                            one_time_use,
                            consumed,
                            confidence_percent,
                            policy_reasons,
                            metadata,
                            checksum,
                            updated_at
                        )
                        VALUES (
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?,
                            ?
                        )
                        """,
                        values,
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError(
                        "Authorization already exists"
                    ) from exc
            else:
                cursor = connection.execute(
                    """
                    UPDATE execution_authorizations
                    SET
                        plan_id = ?,
                        decision_id = ?,
                        source_node_id = ?,
                        requester_payload = ?,
                        approver_payload = ?,
                        risk_class = ?,
                        status = ?,
                        decision = ?,
                        requested_at = ?,
                        approved_at = ?,
                        expires_at = ?,
                        rejection_reason = ?,
                        revocation_reason = ?,
                        dry_run_required = ?,
                        rollback_required = ?,
                        verification_required = ?,
                        execution_allowed = ?,
                        one_time_use = ?,
                        consumed = ?,
                        confidence_percent = ?,
                        policy_reasons = ?,
                        metadata = ?,
                        checksum = ?,
                        updated_at = ?
                    WHERE authorization_id = ?
                    """,
                    (
                        *values[1:],
                        authorization
                        .authorization_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise KeyError(
                        "Authorization not found"
                    )

            connection.commit()

    def _event(
        self,
        authorization_id: str,
        event_type: str,
        *,
        actor: (
            ApprovalIdentity
            | None
        ) = None,
        details: (
            dict[str, Any]
            | None
        ) = None,
    ) -> None:
        with closing(
            self._connect()
        ) as connection:
            connection.execute(
                """
                INSERT INTO
                execution_authorization_events (
                    authorization_id,
                    event_type,
                    event_at,
                    actor_payload,
                    details_payload
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    authorization_id,
                    event_type,
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
                    (
                        canonical_authorization_json(
                            actor.to_dict()
                        )
                        if actor
                        else None
                    ),
                    canonical_authorization_json(
                        details or {}
                    ),
                ),
            )

            connection.commit()

    def create(
        self,
        authorization: ExecutionAuthorization,
    ) -> ExecutionAuthorization:
        if not isinstance(
            authorization,
            ExecutionAuthorization,
        ):
            raise TypeError(
                "create requires an "
                "ExecutionAuthorization"
            )

        self._write(
            authorization,
            insert=True,
        )

        self._event(
            authorization.authorization_id,
            "created",
            actor=authorization.requester,
            details={
                "status":
                    authorization.status.value,
                "decision":
                    authorization.decision.value,
                "risk_class":
                    authorization
                    .risk_class.value,
            },
        )

        return authorization

    def get(
        self,
        authorization_id: str,
    ) -> ExecutionAuthorization | None:
        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            raise ValueError(
                "authorization_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_authorizations
                WHERE authorization_id = ?
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

    def list_authorizations(
        self,
        *,
        status: AuthorizationStatus | None = None,
        source_node_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExecutionAuthorization]:
        limit = max(
            1,
            min(
                int(limit),
                1000,
            ),
        )

        offset = max(
            int(offset),
            0,
        )

        clauses: list[str] = []
        parameters: list[Any] = []

        if status is not None:
            clauses.append(
                "status = ?"
            )

            parameters.append(
                status.value
            )

        if source_node_id:
            clauses.append(
                "source_node_id = ?"
            )

            parameters.append(
                str(
                    source_node_id
                ).strip()
            )

        where = (
            " WHERE "
            + " AND ".join(clauses)
            if clauses
            else ""
        )

        parameters.extend([
            limit,
            offset,
        ])

        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM execution_authorizations
                {where}
                ORDER BY requested_at DESC
                LIMIT ?
                OFFSET ?
                """,
                parameters,
            ).fetchall()

        return [
            self._record_from_row(row)
            for row in rows
        ]

    def count(
        self,
        *,
        status: AuthorizationStatus | None = None,
    ) -> int:
        if status is None:
            query = """
                SELECT COUNT(*) AS total
                FROM execution_authorizations
            """

            parameters: tuple[Any, ...] = ()
        else:
            query = """
                SELECT COUNT(*) AS total
                FROM execution_authorizations
                WHERE status = ?
            """

            parameters = (
                status.value,
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                query,
                parameters,
            ).fetchone()

        return int(
            row["total"]
            if row is not None
            else 0
        )

    def verify(
        self,
        authorization_id: str,
    ) -> bool:
        """
        Verify persisted content directly from the raw SQLite row.

        Integrity verification must not deserialize the row into the
        validated domain model first. A tampered row may be internally
        inconsistent, and that inconsistency is exactly what the
        checksum verification must detect safely.
        """

        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            raise ValueError(
                "authorization_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM execution_authorizations
                WHERE authorization_id = ?
                """,
                (
                    normalized,
                ),
            ).fetchone()

        if row is None:
            return False

        requester_payload = json.loads(
            row["requester_payload"]
        )

        approver_payload = (
            json.loads(
                row["approver_payload"]
            )
            if row["approver_payload"]
            else None
        )

        persisted_payload = {
            "authorization_id":
                row["authorization_id"],
            "plan_id":
                row["plan_id"],
            "decision_id":
                row["decision_id"],
            "source_node_id":
                row["source_node_id"],
            "requester":
                requester_payload,
            "approver":
                approver_payload,
            "risk_class":
                row["risk_class"],
            "status":
                row["status"],
            "decision":
                row["decision"],
            "requested_at":
                row["requested_at"],
            "approved_at":
                row["approved_at"],
            "expires_at":
                row["expires_at"],
            "rejection_reason":
                row["rejection_reason"],
            "revocation_reason":
                row["revocation_reason"],
            "dry_run_required":
                bool(
                    row["dry_run_required"]
                ),
            "rollback_required":
                bool(
                    row["rollback_required"]
                ),
            "verification_required":
                bool(
                    row[
                        "verification_required"
                    ]
                ),
            "execution_allowed":
                bool(
                    row["execution_allowed"]
                ),
            "one_time_use":
                bool(
                    row["one_time_use"]
                ),
            "consumed":
                bool(
                    row["consumed"]
                ),
            "confidence_percent":
                float(
                    row["confidence_percent"]
                ),
            "policy_reasons":
                json.loads(
                    row["policy_reasons"]
                ),
            "metadata":
                json.loads(
                    row["metadata"]
                ),
        }

        calculated = hashlib.sha256(
            canonical_authorization_json(
                persisted_payload
            ).encode("utf-8")
        ).hexdigest()

        return (
            calculated
            == row["checksum"]
        )

    @staticmethod
    def _role_satisfies(
        actual: ApprovalRole,
        required: ApprovalRole,
    ) -> bool:
        return (
            ROLE_PRIORITY.get(
                actual,
                -1,
            )
            >= ROLE_PRIORITY.get(
                required,
                999,
            )
        )

    def approve(
        self,
        authorization_id: str,
        *,
        approver: ApprovalIdentity,
    ) -> ExecutionAuthorization:
        if not isinstance(
            approver,
            ApprovalIdentity,
        ):
            raise TypeError(
                "approver must be "
                "an ApprovalIdentity"
            )

        authorization = self.get(
            authorization_id
        )

        if authorization is None:
            raise KeyError(
                "Authorization not found"
            )

        if authorization.status != (
            AuthorizationStatus.PENDING
        ):
            raise ValueError(
                "Only pending authorization "
                "can be approved"
            )

        if authorization.is_expired:
            expired = replace(
                authorization,
                status=(
                    AuthorizationStatus.EXPIRED
                ),
                execution_allowed=False,
            )

            self._write(
                expired,
                insert=False,
            )

            self._event(
                authorization_id,
                "expired",
            )

            raise ValueError(
                "Authorization has expired"
            )

        required_role = ApprovalRole(
            authorization.metadata.get(
                "required_role",
                ApprovalRole
                .ADMINISTRATOR.value,
            )
        )

        if not self._role_satisfies(
            approver.role,
            required_role,
        ):
            raise PermissionError(
                "Approver role is insufficient"
            )

        approved = replace(
            authorization,
            status=(
                AuthorizationStatus.APPROVED
            ),
            decision=(
                AuthorizationDecision.ALLOW
            ),
            approver=approver,
            approved_at=datetime.now(
                timezone.utc
            ),
            execution_allowed=True,
            rejection_reason=None,
        )

        self._write(
            approved,
            insert=False,
        )

        self._event(
            authorization_id,
            "approved",
            actor=approver,
            details={
                "required_role":
                    required_role.value,
            },
        )

        return approved

    def get_record_version(
        self,
        authorization_id: str,
    ) -> int:
        normalized = str(
            authorization_id
        ).strip()

        if not normalized:
            raise ValueError(
                "authorization_id must not be empty"
            )

        with closing(
            self._connect()
        ) as connection:
            row = connection.execute(
                """
                SELECT record_version
                FROM execution_authorizations
                WHERE authorization_id = ?
                """,
                (
                    normalized,
                ),
            ).fetchone()

        if row is None:
            raise KeyError(
                "Authorization not found"
            )

        return int(
            row["record_version"]
        )

    def approve_atomic(
        self,
        authorization_id: str,
        *,
        approver: ApprovalIdentity,
        expected_version: int,
        idempotency_key: str,
    ) -> AuthorizationMutationResult:
        """
        Approve an authorization using one atomic SQLite transaction.

        The idempotency record, authorization update, checksum update,
        and lifecycle event are committed together.
        """

        if not isinstance(
            approver,
            ApprovalIdentity,
        ):
            raise TypeError(
                "approver must be "
                "an ApprovalIdentity"
            )

        token = AuthorizationMutationToken(
            authorization_id=
                authorization_id,
            action=(
                AuthorizationMutationAction
                .APPROVE
            ),
            expected_version=
                expected_version,
            idempotency_key=
                idempotency_key,
            actor_identity_id=
                approver.identity_id,
            payload={
                "approver":
                    approver.to_dict(),
            },
        )

        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            replay_row = connection.execute(
                """
                SELECT *
                FROM
                    execution_authorization_idempotency
                WHERE idempotency_key = ?
                """,
                (
                    token.idempotency_key,
                ),
            ).fetchone()

            if replay_row is not None:
                if (
                    replay_row[
                        "request_fingerprint"
                    ]
                    != token.request_fingerprint
                ):
                    raise IdempotencyConflict(
                        idempotency_key=
                            token.idempotency_key
                    )

                connection.commit()

                return AuthorizationMutationResult(
                    authorization_id=
                        replay_row[
                            "authorization_id"
                        ],
                    action=(
                        AuthorizationMutationAction(
                            replay_row["action"]
                        )
                    ),
                    previous_version=int(
                        replay_row[
                            "previous_version"
                        ]
                    ),
                    current_version=int(
                        replay_row[
                            "current_version"
                        ]
                    ),
                    disposition=(
                        IdempotencyDisposition
                        .REPLAY
                    ),
                    idempotency_key=
                        token.idempotency_key,
                    request_fingerprint=
                        token.request_fingerprint,
                    response_payload=json.loads(
                        replay_row[
                            "response_payload"
                        ]
                    ),
                )

            row = connection.execute(
                """
                SELECT *
                FROM execution_authorizations
                WHERE authorization_id = ?
                """,
                (
                    token.authorization_id,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Authorization not found"
                )

            actual_version = int(
                row["record_version"]
            )

            if (
                actual_version
                != token.expected_version
            ):
                raise AuthorizationVersionConflict(
                    authorization_id=
                        token.authorization_id,
                    expected_version=
                        token.expected_version,
                    actual_version=
                        actual_version,
                )

            authorization = (
                self._record_from_row(
                    row
                )
            )

            if authorization.status != (
                AuthorizationStatus.PENDING
            ):
                raise ValueError(
                    "Only pending authorization "
                    "can be approved"
                )

            if authorization.is_expired:
                raise ValueError(
                    "Authorization has expired"
                )

            required_role = ApprovalRole(
                authorization.metadata.get(
                    "required_role",
                    ApprovalRole
                    .ADMINISTRATOR.value,
                )
            )

            if not self._role_satisfies(
                approver.role,
                required_role,
            ):
                raise PermissionError(
                    "Approver role is insufficient"
                )

            approved = replace(
                authorization,
                status=(
                    AuthorizationStatus.APPROVED
                ),
                decision=(
                    AuthorizationDecision.ALLOW
                ),
                approver=approver,
                approved_at=datetime.now(
                    timezone.utc
                ),
                execution_allowed=True,
                rejection_reason=None,
            )

            checksum = (
                calculate_authorization_checksum(
                    approved
                )
            )

            updated_at = datetime.now(
                timezone.utc
            ).isoformat()

            current_version = (
                actual_version + 1
            )

            cursor = connection.execute(
                """
                UPDATE execution_authorizations
                SET
                    approver_payload = ?,
                    status = ?,
                    decision = ?,
                    approved_at = ?,
                    rejection_reason = ?,
                    execution_allowed = ?,
                    checksum = ?,
                    updated_at = ?,
                    record_version =
                        record_version + 1
                WHERE authorization_id = ?
                  AND status = ?
                  AND record_version = ?
                """,
                (
                    canonical_authorization_json(
                        approver.to_dict()
                    ),
                    approved.status.value,
                    approved.decision.value,
                    approved.approved_at
                    .isoformat(),
                    approved.rejection_reason,
                    int(
                        approved.execution_allowed
                    ),
                    checksum,
                    updated_at,
                    token.authorization_id,
                    AuthorizationStatus
                    .PENDING.value,
                    token.expected_version,
                ),
            )

            if cursor.rowcount != 1:
                current_row = (
                    connection.execute(
                        """
                        SELECT record_version
                        FROM execution_authorizations
                        WHERE authorization_id = ?
                        """,
                        (
                            token
                            .authorization_id,
                        ),
                    ).fetchone()
                )

                actual = (
                    int(
                        current_row[
                            "record_version"
                        ]
                    )
                    if current_row
                    else actual_version
                )

                raise AuthorizationVersionConflict(
                    authorization_id=
                        token.authorization_id,
                    expected_version=
                        token.expected_version,
                    actual_version=actual,
                )

            response_payload = (
                approved.to_dict()
            )

            response_payload[
                "record_version"
            ] = current_version

            connection.execute(
                """
                INSERT INTO
                execution_authorization_idempotency (
                    idempotency_key,
                    authorization_id,
                    action,
                    request_fingerprint,
                    previous_version,
                    current_version,
                    response_payload,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token.idempotency_key,
                    token.authorization_id,
                    token.action.value,
                    token.request_fingerprint,
                    actual_version,
                    current_version,
                    canonical_authorization_json(
                        response_payload
                    ),
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
                ),
            )

            connection.execute(
                """
                INSERT INTO
                execution_authorization_events (
                    authorization_id,
                    event_type,
                    event_at,
                    actor_payload,
                    details_payload
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    token.authorization_id,
                    "approved",
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
                    canonical_authorization_json(
                        approver.to_dict()
                    ),
                    canonical_authorization_json({
                        "required_role":
                            required_role.value,
                        "previous_version":
                            actual_version,
                        "current_version":
                            current_version,
                        "idempotency_key":
                            token
                            .idempotency_key,
                    }),
                ),
            )

            connection.commit()

            return AuthorizationMutationResult(
                authorization_id=
                    token.authorization_id,
                action=token.action,
                previous_version=
                    actual_version,
                current_version=
                    current_version,
                disposition=(
                    IdempotencyDisposition.NEW
                ),
                idempotency_key=
                    token.idempotency_key,
                request_fingerprint=
                    token.request_fingerprint,
                response_payload=
                    response_payload,
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def reject(
        self,
        authorization_id: str,
        *,
        approver: ApprovalIdentity,
        reason: str,
    ) -> ExecutionAuthorization:
        normalized_reason = str(
            reason
        ).strip()

        if not normalized_reason:
            raise ValueError(
                "Rejection reason is required"
            )

        authorization = self.get(
            authorization_id
        )

        if authorization is None:
            raise KeyError(
                "Authorization not found"
            )

        if authorization.status != (
            AuthorizationStatus.PENDING
        ):
            raise ValueError(
                "Only pending authorization "
                "can be rejected"
            )

        rejected = replace(
            authorization,
            status=(
                AuthorizationStatus.REJECTED
            ),
            decision=(
                AuthorizationDecision.DENY
            ),
            approver=approver,
            rejection_reason=
                normalized_reason,
            execution_allowed=False,
        )

        self._write(
            rejected,
            insert=False,
        )

        self._event(
            authorization_id,
            "rejected",
            actor=approver,
            details={
                "reason":
                    normalized_reason,
            },
        )

        return rejected

    def revoke(
        self,
        authorization_id: str,
        *,
        actor: ApprovalIdentity,
        reason: str,
    ) -> ExecutionAuthorization:
        normalized_reason = str(
            reason
        ).strip()

        if not normalized_reason:
            raise ValueError(
                "Revocation reason is required"
            )

        authorization = self.get(
            authorization_id
        )

        if authorization is None:
            raise KeyError(
                "Authorization not found"
            )

        if authorization.status != (
            AuthorizationStatus.APPROVED
        ):
            raise ValueError(
                "Only approved authorization "
                "can be revoked"
            )

        revoked = replace(
            authorization,
            status=(
                AuthorizationStatus.REVOKED
            ),
            decision=(
                AuthorizationDecision.DENY
            ),
            revocation_reason=
                normalized_reason,
            execution_allowed=False,
            consumed=False,
        )

        self._write(
            revoked,
            insert=False,
        )

        self._event(
            authorization_id,
            "revoked",
            actor=actor,
            details={
                "reason":
                    normalized_reason,
            },
        )

        return revoked

    def consume(
        self,
        authorization_id: str,
    ) -> ExecutionAuthorization:
        authorization = self.get(
            authorization_id
        )

        if authorization is None:
            raise KeyError(
                "Authorization not found"
            )

        if not authorization.is_usable:
            raise ValueError(
                "Authorization is not usable"
            )

        consumed = replace(
            authorization,
            status=AuthorizationStatus.USED,
            execution_allowed=False,
            consumed=True,
        )

        self._write(
            consumed,
            insert=False,
        )

        self._event(
            authorization_id,
            "consumed",
            details={
                "one_time_use":
                    authorization.one_time_use,
            },
        )

        return consumed

    def expire_due(
        self,
    ) -> int:
        now = datetime.now(
            timezone.utc
        )

        candidates = (
            self.list_authorizations(
                limit=1000
            )
        )

        expired_count = 0

        for authorization in candidates:
            if authorization.status not in {
                AuthorizationStatus.PENDING,
                AuthorizationStatus.APPROVED,
            }:
                continue

            if (
                authorization.expires_at
                is None
                or authorization.expires_at
                > now
            ):
                continue

            expired = replace(
                authorization,
                status=(
                    AuthorizationStatus.EXPIRED
                ),
                execution_allowed=False,
            )

            self._write(
                expired,
                insert=False,
            )

            self._event(
                authorization.authorization_id,
                "expired",
            )

            expired_count += 1

        return expired_count

    def events(
        self,
        authorization_id: str,
    ) -> list[dict[str, Any]]:
        with closing(
            self._connect()
        ) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM execution_authorization_events
                WHERE authorization_id = ?
                ORDER BY event_at ASC, event_id ASC
                """,
                (
                    authorization_id,
                ),
            ).fetchall()

        return [
            {
                "event_id":
                    row["event_id"],
                "authorization_id":
                    row["authorization_id"],
                "event_type":
                    row["event_type"],
                "event_at":
                    row["event_at"],
                "actor": (
                    json.loads(
                        row["actor_payload"]
                    )
                    if row["actor_payload"]
                    else None
                ),
                "details":
                    json.loads(
                        row["details_payload"]
                    ),
            }
            for row in rows
        ]
