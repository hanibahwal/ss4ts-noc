from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.noc_wall_dashboard_store import (
    GENESIS_RECORD_HASH,
    NOCWallDashboardRecord,
    NOCWallDashboardStore,
)


FINAL_SERVICE_NAME = (
    "SS4TS NOC Wall Dashboard Final Audit"
)

FINAL_SERVICE_VERSION = "1.0.0"

UI_RENDERER_NAME = (
    "SS4TS NOC Wall Dashboard HTML Renderer"
)

UI_RENDERER_VERSION = "1.0.0"


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
    *,
    field_name: str,
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
            f"{field_name} must be a datetime"
        )

    if (
        resolved.tzinfo is None
        or resolved.utcoffset() is None
    ):
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )

    return resolved.astimezone(
        timezone.utc
    )


def _sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(
        value
    ).hexdigest()


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardFinalAuditReport:
    audit_id: str
    audit_valid: bool

    record_count: int
    first_sequence_number: int | None
    last_sequence_number: int | None

    first_record_hash: str | None
    last_record_hash: str | None

    latest_dashboard_id: str | None
    latest_dashboard_fingerprint: str | None

    checks: dict[str, bool]
    audit_errors: tuple[str, ...]
    audit_warnings: tuple[str, ...]

    audited_at: datetime

    auditor_name: str = (
        FINAL_SERVICE_NAME
    )

    auditor_version: str = (
        FINAL_SERVICE_VERSION
    )

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

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "audit_id":
                self.audit_id,
            "audit_valid":
                self.audit_valid,
            "record_count":
                self.record_count,
            "first_sequence_number":
                self.first_sequence_number,
            "last_sequence_number":
                self.last_sequence_number,
            "first_record_hash":
                self.first_record_hash,
            "last_record_hash":
                self.last_record_hash,
            "latest_dashboard_id":
                self.latest_dashboard_id,
            "latest_dashboard_fingerprint":
                self.latest_dashboard_fingerprint,
            "checks":
                dict(
                    self.checks
                ),
            "audit_errors":
                list(
                    self.audit_errors
                ),
            "audit_warnings":
                list(
                    self.audit_warnings
                ),
            "audited_at":
                self.audited_at.isoformat(),
            "auditor_name":
                self.auditor_name,
            "auditor_version":
                self.auditor_version,
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
                "audit_only":
                    True,
                "read_only":
                    True,
                "store_mutated":
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


@dataclass(
    frozen=True,
    slots=True,
)
class NOCWallDashboardHTMLExport:
    dashboard_id: str
    dashboard_fingerprint: str

    output_path: str
    html_sha256: str
    html_size_bytes: int

    rendered_at: datetime

    renderer_name: str = (
        UI_RENDERER_NAME
    )

    renderer_version: str = (
        UI_RENDERER_VERSION
    )

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

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "dashboard_id":
                self.dashboard_id,
            "dashboard_fingerprint":
                self.dashboard_fingerprint,
            "output_path":
                self.output_path,
            "html_sha256":
                self.html_sha256,
            "html_size_bytes":
                self.html_size_bytes,
            "rendered_at":
                self.rendered_at.isoformat(),
            "renderer_name":
                self.renderer_name,
            "renderer_version":
                self.renderer_version,
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
                "display_only":
                    True,
                "static_html":
                    True,
                "store_mutated":
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
                "network_device_access":
                    False,
                "command_generated":
                    False,
                "device_command_executed":
                    False,
            },
        }


class NOCWallDashboardFinalAuditor:
    REQUIRED_CHECKS = (
        "store_chain_valid",
        "sequence_numbers_valid",
        "previous_hash_links_valid",
        "record_hashes_valid",
        "snapshot_bindings_valid",
        "validation_bindings_valid",
        "timestamp_order_valid",
        "store_identity_valid",
        "safety_guarantees_valid",
    )

    @staticmethod
    def _timestamp_order_valid(
        record: NOCWallDashboardRecord,
        audited_at: datetime,
    ) -> bool:
        try:
            generated_at = datetime.fromisoformat(
                record.generated_at
            )

            validated_at = datetime.fromisoformat(
                record.validation_payload[
                    "validated_at"
                ]
            )

            stored_at = datetime.fromisoformat(
                record.stored_at
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return False

        values = (
            generated_at,
            validated_at,
            stored_at,
        )

        if any(
            value.tzinfo is None
            or value.utcoffset() is None
            for value in values
        ):
            return False

        generated_utc = generated_at.astimezone(
            timezone.utc
        )

        validated_utc = validated_at.astimezone(
            timezone.utc
        )

        stored_utc = stored_at.astimezone(
            timezone.utc
        )

        return (
            generated_utc
            <= validated_utc
            <= stored_utc
            <= audited_at
        )

    @staticmethod
    def _safety_valid(
        payload: dict[str, Any],
    ) -> bool:
        return all(
            (
                payload.get(
                    "incident_created"
                )
                is False,
                payload.get(
                    "recommendation_executed"
                )
                is False,
                payload.get(
                    "decision_created"
                )
                is False,
                payload.get(
                    "authorization_created"
                )
                is False,
                payload.get(
                    "execution_allowed"
                )
                is False,
                payload.get(
                    "can_execute"
                )
                is False,
            )
        )

    @staticmethod
    def _audit_id(
        *,
        record_count: int,
        first_record_hash: str | None,
        last_record_hash: str | None,
        audited_at: datetime,
    ) -> str:
        payload = {
            "record_count":
                record_count,
            "first_record_hash":
                first_record_hash,
            "last_record_hash":
                last_record_hash,
            "audited_at":
                audited_at.isoformat(),
            "auditor_name":
                FINAL_SERVICE_NAME,
            "auditor_version":
                FINAL_SERVICE_VERSION,
        }

        digest = hashlib.sha256(
            _canonical_json(
                payload
            ).encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            "noc-wall-dashboard-final-audit:"
            f"{digest}"
        )

    def verify(
        self,
        *,
        store: NOCWallDashboardStore,
        audited_at: datetime | None = None,
    ) -> NOCWallDashboardFinalAuditReport:
        if not isinstance(
            store,
            NOCWallDashboardStore,
        ):
            raise TypeError(
                "store must be a "
                "NOCWallDashboardStore"
            )

        resolved_audited_at = (
            _normalize_datetime(
                audited_at,
                field_name="audited_at",
            )
        )

        records = store.list_records(
            limit=1_000_000
        )

        checks = {
            check_name: True
            for check_name
            in self.REQUIRED_CHECKS
        }

        errors: list[str] = []
        warnings: list[str] = []

        checks[
            "store_chain_valid"
        ] = store.verify_chain()

        expected_sequence = 1
        expected_previous_hash = (
            GENESIS_RECORD_HASH
        )

        for record in records:
            if (
                record.sequence_number
                != expected_sequence
            ):
                checks[
                    "sequence_numbers_valid"
                ] = False

            if (
                record.previous_record_hash
                != expected_previous_hash
            ):
                checks[
                    "previous_hash_links_valid"
                ] = False

            if not record.verify_hash():
                checks[
                    "record_hashes_valid"
                ] = False

            snapshot_payload = (
                record.snapshot_payload
            )

            validation_payload = (
                record.validation_payload
            )

            if not all(
                (
                    snapshot_payload.get(
                        "dashboard_id"
                    )
                    == record.dashboard_id,
                    snapshot_payload.get(
                        "dashboard_fingerprint"
                    )
                    == record.dashboard_fingerprint,
                    snapshot_payload.get(
                        "overall_status"
                    )
                    == record.overall_status,
                    snapshot_payload.get(
                        "overall_health_score"
                    )
                    == record.overall_health_score,
                    snapshot_payload.get(
                        "overall_trend"
                    )
                    == record.overall_trend,
                )
            ):
                checks[
                    "snapshot_bindings_valid"
                ] = False

            if not all(
                (
                    record.validation_valid,
                    record.dashboard_accepted,
                    validation_payload.get(
                        "validation_id"
                    )
                    == record.validation_id,
                    validation_payload.get(
                        "dashboard_id"
                    )
                    == record.dashboard_id,
                    validation_payload.get(
                        "dashboard_fingerprint"
                    )
                    == record.dashboard_fingerprint,
                    validation_payload.get(
                        "validation_valid"
                    )
                    is True,
                    validation_payload.get(
                        "dashboard_accepted"
                    )
                    is True,
                )
            ):
                checks[
                    "validation_bindings_valid"
                ] = False

            if not self._timestamp_order_valid(
                record,
                resolved_audited_at,
            ):
                checks[
                    "timestamp_order_valid"
                ] = False

            if not all(
                (
                    record.store_name
                    == (
                        "SS4TS Immutable "
                        "NOC Wall Dashboard Store"
                    ),
                    record.store_version
                    == "1.0.0",
                )
            ):
                checks[
                    "store_identity_valid"
                ] = False

            if not all(
                (
                    self._safety_valid(
                        snapshot_payload
                    ),
                    self._safety_valid(
                        validation_payload
                    ),
                    self._safety_valid(
                        record.to_dict()
                    ),
                )
            ):
                checks[
                    "safety_guarantees_valid"
                ] = False

            expected_sequence += 1
            expected_previous_hash = (
                record.record_hash
            )

        if not records:
            warnings.append(
                "NOC wall dashboard store is empty"
            )

        for check_name in self.REQUIRED_CHECKS:
            if not checks.get(
                check_name,
                False,
            ):
                errors.append(
                    f"{check_name} failed"
                )

        audit_valid = (
            not errors
            and all(
                checks.values()
            )
        )

        first_record = (
            records[0]
            if records
            else None
        )

        last_record = (
            records[-1]
            if records
            else None
        )

        return NOCWallDashboardFinalAuditReport(
            audit_id=self._audit_id(
                record_count=len(
                    records
                ),
                first_record_hash=(
                    first_record.record_hash
                    if first_record
                    else None
                ),
                last_record_hash=(
                    last_record.record_hash
                    if last_record
                    else None
                ),
                audited_at=(
                    resolved_audited_at
                ),
            ),
            audit_valid=(
                audit_valid
            ),
            record_count=len(
                records
            ),
            first_sequence_number=(
                first_record.sequence_number
                if first_record
                else None
            ),
            last_sequence_number=(
                last_record.sequence_number
                if last_record
                else None
            ),
            first_record_hash=(
                first_record.record_hash
                if first_record
                else None
            ),
            last_record_hash=(
                last_record.record_hash
                if last_record
                else None
            ),
            latest_dashboard_id=(
                last_record.dashboard_id
                if last_record
                else None
            ),
            latest_dashboard_fingerprint=(
                last_record.dashboard_fingerprint
                if last_record
                else None
            ),
            checks=checks,
            audit_errors=tuple(
                errors
            ),
            audit_warnings=tuple(
                warnings
            ),
            audited_at=(
                resolved_audited_at
            ),
        )


class NOCWallDashboardHTMLRenderer:
    @staticmethod
    def _status_class(
        status: str,
    ) -> str:
        normalized = str(
            status
        ).strip().lower()

        if normalized in {
            "healthy",
            "degraded",
            "critical",
            "unknown",
        }:
            return normalized

        return "unknown"

    @staticmethod
    def _metric_card(
        title: str,
        value: Any,
        subtitle: str,
    ) -> str:
        return f"""
        <section class="metric-card">
            <span class="metric-title">{escape(title)}</span>
            <strong class="metric-value">{escape(str(value))}</strong>
            <span class="metric-subtitle">{escape(subtitle)}</span>
        </section>
        """.strip()

    def render_html(
        self,
        *,
        record: NOCWallDashboardRecord,
        audit: NOCWallDashboardFinalAuditReport,
        rendered_at: datetime,
    ) -> str:
        if not isinstance(
            record,
            NOCWallDashboardRecord,
        ):
            raise TypeError(
                "record must be a "
                "NOCWallDashboardRecord"
            )

        if not isinstance(
            audit,
            NOCWallDashboardFinalAuditReport,
        ):
            raise TypeError(
                "audit must be a "
                "NOCWallDashboardFinalAuditReport"
            )

        if not audit.audit_valid:
            raise ValueError(
                "Final dashboard audit is invalid"
            )

        if (
            audit.latest_dashboard_id
            != record.dashboard_id
        ):
            raise ValueError(
                "Audit latest dashboard binding "
                "is invalid"
            )

        payload = record.snapshot_payload

        alerts = payload.get(
            "alerts",
            [],
        )

        affected_sites = payload.get(
            "affected_sites",
            [],
        )

        alerts_html = "".join(
            f"""
            <li class="alert-item alert-{escape(str(alert.get('severity', 'info')))}">
                <strong>{escape(str(alert.get('title', 'Alert')))}</strong>
                <span>{escape(str(alert.get('message', '')))}</span>
            </li>
            """.strip()
            for alert in alerts
        )

        if not alerts_html:
            alerts_html = (
                '<li class="alert-item alert-info">'
                "<strong>No active alerts</strong>"
                "<span>The latest snapshot contains "
                "no dashboard alerts.</span>"
                "</li>"
            )

        sites_html = "".join(
            f"<li>{escape(str(site))}</li>"
            for site in affected_sites
        )

        if not sites_html:
            sites_html = (
                "<li>No affected sites</li>"
            )

        metric_cards = "".join(
            (
                self._metric_card(
                    "Health Score",
                    record.overall_health_score,
                    "Overall operational health",
                ),
                self._metric_card(
                    "Sites",
                    record.total_sites,
                    "Monitored sites",
                ),
                self._metric_card(
                    "Devices",
                    record.total_devices,
                    "Monitored devices",
                ),
                self._metric_card(
                    "Links",
                    record.total_links,
                    "Monitored links",
                ),
                self._metric_card(
                    "Incidents",
                    record.active_incidents,
                    "Active incidents",
                ),
                self._metric_card(
                    "Predictions",
                    record.active_predictions,
                    "Active predictions",
                ),
                self._metric_card(
                    "Approvals",
                    record.pending_human_approvals,
                    "Pending human approvals",
                ),
            )
        )

        status_class = self._status_class(
            record.overall_status
        )

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>SS4TS NOC Wall Dashboard</title>
<style>
:root {{
    color-scheme: dark;
    font-family: Inter, Arial, sans-serif;
}}
* {{
    box-sizing: border-box;
}}
body {{
    margin: 0;
    min-height: 100vh;
    background: #07101f;
    color: #f8fafc;
}}
.dashboard {{
    width: 100%;
    min-height: 100vh;
    padding: 24px;
}}
.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 18px;
    margin-bottom: 20px;
}}
.title {{
    margin: 0;
    font-size: clamp(24px, 3vw, 48px);
}}
.subtitle {{
    margin-top: 8px;
    color: #94a3b8;
}}
.status {{
    padding: 14px 22px;
    border-radius: 999px;
    font-weight: 800;
    text-transform: uppercase;
}}
.status.healthy {{
    background: #064e3b;
    color: #6ee7b7;
}}
.status.degraded {{
    background: #78350f;
    color: #fde68a;
}}
.status.critical {{
    background: #7f1d1d;
    color: #fecaca;
}}
.status.unknown {{
    background: #334155;
    color: #cbd5e1;
}}
.metrics {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
}}
.metric-card,
.panel {{
    border: 1px solid #1e293b;
    background: #0f172a;
    border-radius: 18px;
    padding: 18px;
}}
.metric-title,
.metric-subtitle {{
    display: block;
    color: #94a3b8;
}}
.metric-value {{
    display: block;
    margin: 8px 0;
    font-size: clamp(28px, 4vw, 54px);
}}
.panels {{
    display: grid;
    grid-template-columns:
        minmax(0, 2fr) minmax(260px, 1fr);
    gap: 14px;
    margin-top: 14px;
}}
.panel h2 {{
    margin-top: 0;
}}
.alert-list,
.site-list {{
    padding: 0;
    margin: 0;
    list-style: none;
}}
.alert-item {{
    display: grid;
    gap: 4px;
    margin-bottom: 10px;
    padding: 12px;
    border-left: 5px solid #64748b;
    background: #111827;
    border-radius: 10px;
}}
.alert-critical {{
    border-left-color: #ef4444;
}}
.alert-high {{
    border-left-color: #f97316;
}}
.alert-warning {{
    border-left-color: #eab308;
}}
.alert-info {{
    border-left-color: #38bdf8;
}}
.site-list li {{
    padding: 9px 0;
    border-bottom: 1px solid #1e293b;
}}
.footer {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    justify-content: space-between;
    margin-top: 16px;
    color: #64748b;
    font-size: 13px;
}}
@media (max-width: 850px) {{
    .header,
    .panels {{
        grid-template-columns: 1fr;
        display: grid;
    }}
}}
</style>
</head>
<body>
<main class="dashboard">
    <header class="header">
        <div>
            <h1 class="title">SS4TS NOC Wall Dashboard</h1>
            <div class="subtitle">
                Dashboard ID:
                {escape(record.dashboard_id)}
            </div>
        </div>
        <div class="status {status_class}">
            {escape(record.overall_status)}
        </div>
    </header>

    <section class="metrics">
        {metric_cards}
    </section>

    <section class="panels">
        <article class="panel">
            <h2>Active Alerts</h2>
            <ul class="alert-list">
                {alerts_html}
            </ul>
        </article>

        <article class="panel">
            <h2>Affected Sites</h2>
            <ul class="site-list">
                {sites_html}
            </ul>
        </article>
    </section>

    <footer class="footer">
        <span>Trend: {escape(record.overall_trend)}</span>
        <span>Snapshot: {escape(record.generated_at)}</span>
        <span>Stored: {escape(record.stored_at)}</span>
        <span>Rendered: {escape(rendered_at.isoformat())}</span>
        <span>Integrity: verified</span>
    </footer>
</main>
</body>
</html>
"""

    def export(
        self,
        *,
        store: NOCWallDashboardStore,
        output_path: str | Path,
        rendered_at: datetime | None = None,
        overwrite: bool = False,
    ) -> NOCWallDashboardHTMLExport:
        if not isinstance(
            store,
            NOCWallDashboardStore,
        ):
            raise TypeError(
                "store must be a "
                "NOCWallDashboardStore"
            )

        resolved_rendered_at = (
            _normalize_datetime(
                rendered_at,
                field_name="rendered_at",
            )
        )

        audit = (
            NOCWallDashboardFinalAuditor()
            .verify(
                store=store,
                audited_at=resolved_rendered_at,
            )
        )

        if not audit.audit_valid:
            raise ValueError(
                "Final dashboard audit is invalid"
            )

        records = store.list_records(
            limit=1_000_000
        )

        if not records:
            raise ValueError(
                "Dashboard store is empty"
            )

        record = records[-1]

        destination = Path(
            output_path
        )

        if destination.exists() and not overwrite:
            raise FileExistsError(
                f"Output file already exists: "
                f"{destination}"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        html = self.render_html(
            record=record,
            audit=audit,
            rendered_at=resolved_rendered_at,
        )

        html_bytes = html.encode(
            "utf-8"
        )

        temporary_path = (
            destination.parent
            / f".{destination.name}.tmp"
        )

        temporary_path.write_bytes(
            html_bytes
        )

        temporary_path.replace(
            destination
        )

        return NOCWallDashboardHTMLExport(
            dashboard_id=(
                record.dashboard_id
            ),
            dashboard_fingerprint=(
                record.dashboard_fingerprint
            ),
            output_path=str(
                destination
            ),
            html_sha256=(
                _sha256_bytes(
                    html_bytes
                )
            ),
            html_size_bytes=len(
                html_bytes
            ),
            rendered_at=(
                resolved_rendered_at
            ),
        )


def verify_noc_wall_dashboard_store(
    *,
    store: NOCWallDashboardStore,
    audited_at: datetime | None = None,
) -> NOCWallDashboardFinalAuditReport:
    return (
        NOCWallDashboardFinalAuditor()
        .verify(
            store=store,
            audited_at=audited_at,
        )
    )


def export_noc_wall_dashboard_html(
    *,
    store: NOCWallDashboardStore,
    output_path: str | Path,
    rendered_at: datetime | None = None,
    overwrite: bool = False,
) -> NOCWallDashboardHTMLExport:
    return (
        NOCWallDashboardHTMLRenderer()
        .export(
            store=store,
            output_path=output_path,
            rendered_at=rendered_at,
            overwrite=overwrite,
        )
    )
