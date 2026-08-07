from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from app.services.executive_predictive_report_store import (
    ExecutivePredictiveReportIntegrityError,
    ExecutivePredictiveReportRecord,
    ExecutivePredictiveReportStore,
)


PDF_SERVICE_NAME = (
    "SS4TS Executive Predictive Report PDF Renderer"
)

PDF_SERVICE_VERSION = "1.0.0"


class ExecutivePredictiveReportPDFError(
    RuntimeError
):
    pass


class ExecutivePredictiveReportPDFIntegrityError(
    ExecutivePredictiveReportPDFError
):
    pass


class ExecutivePredictiveReportPDFExistsError(
    ExecutivePredictiveReportPDFError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class ExecutivePredictiveReportPDFExport:
    report_id: str
    report_fingerprint: str
    source_record_hash: str

    output_path: str
    file_name: str

    content_type: str
    file_size_bytes: int
    page_count: int
    pdf_sha256: str

    exported_at: datetime
    renderer_name: str
    renderer_version: str

    @property
    def pdf_rendered(
        self,
    ) -> bool:
        return True

    @property
    def report_created(
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

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "report_id":
                self.report_id,
            "report_fingerprint":
                self.report_fingerprint,
            "source_record_hash":
                self.source_record_hash,
            "output_path":
                self.output_path,
            "file_name":
                self.file_name,
            "content_type":
                self.content_type,
            "file_size_bytes":
                self.file_size_bytes,
            "page_count":
                self.page_count,
            "pdf_sha256":
                self.pdf_sha256,
            "exported_at":
                self.exported_at.isoformat(),
            "renderer_name":
                self.renderer_name,
            "renderer_version":
                self.renderer_version,
            "pdf_rendered":
                True,
            "report_created":
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
                "render_only":
                    True,
                "stored_report_only":
                    True,
                "source_chain_verified":
                    True,
                "source_record_verified":
                    True,
                "report_mutated":
                    False,
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
                "authorization_approved":
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


def _safe_pdf_text(
    value: Any,
) -> str:
    text = str(
        value
    )

    text = (
        text.replace(
            "\\",
            "\\\\",
        )
        .replace(
            "(",
            "\\(",
        )
        .replace(
            ")",
            "\\)",
        )
        .replace(
            "\r",
            " ",
        )
        .replace(
            "\n",
            " ",
        )
    )

    return text.encode(
        "latin-1",
        errors="replace",
    ).decode(
        "latin-1"
    )


def _wrap_text(
    value: Any,
    *,
    width: int = 92,
) -> tuple[str, ...]:
    text = " ".join(
        str(
            value
        ).split()
    )

    if not text:
        return ("",)

    words = text.split(" ")

    lines: list[str] = []
    current = ""

    for word in words:
        candidate = (
            word
            if not current
            else f"{current} {word}"
        )

        if len(
            candidate
        ) <= width:
            current = candidate
            continue

        if current:
            lines.append(
                current
            )

        while len(
            word
        ) > width:
            lines.append(
                word[:width]
            )
            word = word[width:]

        current = word

    if current:
        lines.append(
            current
        )

    return tuple(
        lines
    )


def _append_section(
    lines: list[str],
    title: str,
    values: Iterable[Any],
) -> None:
    normalized_values = tuple(
        value
        for value in values
        if str(
            value
        ).strip()
    )

    if not normalized_values:
        return

    lines.append("")
    lines.append(
        title.upper()
    )
    lines.append(
        "-" * min(
            92,
            max(
                8,
                len(
                    title
                ),
            ),
        )
    )

    for value in normalized_values:
        wrapped = _wrap_text(
            value,
            width=88,
        )

        if wrapped:
            lines.append(
                f"- {wrapped[0]}"
            )

            for continuation in wrapped[1:]:
                lines.append(
                    f"  {continuation}"
                )


def _build_report_lines(
    record: ExecutivePredictiveReportRecord,
    exported_at: datetime,
) -> tuple[str, ...]:
    payload = record.report_payload

    lines: list[str] = [
        "SS4TS EXECUTIVE PREDICTIVE REPORT",
        "=" * 40,
        "",
        str(
            record.report_title
        ),
        "",
        (
            f"Report ID: "
            f"{record.report_id}"
        ),
        (
            f"Report Type: "
            f"{record.report_type}"
        ),
        (
            f"Period: "
            f"{record.report_period_start} "
            f"to {record.report_period_end}"
        ),
        (
            f"Generated At: "
            f"{record.generated_at}"
        ),
        (
            f"Exported At: "
            f"{exported_at.isoformat()}"
        ),
        "",
        "EXECUTIVE STATUS",
        "----------------",
        (
            f"Overall Risk: "
            f"{record.overall_risk_class.upper()}"
        ),
        (
            f"Health Score: "
            f"{record.overall_health_score:.2f}/100"
        ),
        (
            f"Service Outlook: "
            f"{record.service_outlook.upper()}"
        ),
        (
            f"Predictions: "
            f"{record.prediction_count}"
        ),
        (
            f"Critical Predictions: "
            f"{record.critical_prediction_count}"
        ),
        (
            f"High-Risk Predictions: "
            f"{record.high_risk_prediction_count}"
        ),
        "",
        "EXECUTIVE SUMMARY",
        "-----------------",
    ]

    lines.extend(
        _wrap_text(
            payload.get(
                "executive_summary",
                "",
            )
        )
    )

    _append_section(
        lines,
        "Key Findings",
        payload.get(
            "key_findings",
            (),
        ),
    )

    _append_section(
        lines,
        "Risk Highlights",
        payload.get(
            "risk_highlights",
            (),
        ),
    )

    _append_section(
        lines,
        "Capacity Forecast",
        payload.get(
            "capacity_forecast",
            (),
        ),
    )

    _append_section(
        lines,
        "Recommended Priorities",
        payload.get(
            "recommended_priorities",
            (),
        ),
    )

    _append_section(
        lines,
        "Affected Sites",
        record.report_payload.get(
            "affected_sites",
            (),
        ),
    )

    _append_section(
        lines,
        "Affected Devices",
        record.report_payload.get(
            "affected_devices",
            (),
        ),
    )

    _append_section(
        lines,
        "Affected Links",
        record.report_payload.get(
            "affected_links",
            (),
        ),
    )

    _append_section(
        lines,
        "Affected Services",
        record.report_payload.get(
            "affected_services",
            (),
        ),
    )

    lines.extend(
        (
            "",
            "SOURCE INTEGRITY",
            "----------------",
            (
                f"Report Fingerprint: "
                f"{record.report_fingerprint}"
            ),
            (
                f"Source Audit ID: "
                f"{record.source_audit_id}"
            ),
            (
                f"Source Audit Valid: "
                f"{record.source_audit_valid}"
            ),
            (
                f"Store Record Hash: "
                f"{record.record_hash}"
            ),
            (
                f"Previous Record Hash: "
                f"{record.previous_record_hash}"
            ),
            (
                f"Schema Version: "
                f"{record.schema_version}"
            ),
            (
                f"Generated By: "
                f"{record.generated_by}"
            ),
            "",
            "SAFETY NOTICE",
            "-------------",
            (
                "This document is an executive "
                "predictive report export only."
            ),
            (
                "It does not create an incident, "
                "decision, authorization, command, "
                "or permission to execute."
            ),
        )
    )

    return tuple(
        lines
    )


def _paginate(
    lines: tuple[str, ...],
    *,
    lines_per_page: int = 48,
) -> tuple[
    tuple[str, ...],
    ...,
]:
    if lines_per_page <= 0:
        raise ValueError(
            "lines_per_page must be positive"
        )

    pages = tuple(
        lines[index:index + lines_per_page]
        for index in range(
            0,
            len(
                lines
            ),
            lines_per_page,
        )
    )

    return pages or (
        ("",),
    )


def _pdf_stream_for_page(
    lines: tuple[str, ...],
    *,
    page_number: int,
    page_count: int,
) -> bytes:
    commands: list[str] = [
        "BT",
        "/F1 10 Tf",
        "50 790 Td",
        "12 TL",
    ]

    for index, line in enumerate(
        lines
    ):
        if index:
            commands.append(
                "T*"
            )

        commands.append(
            f"({_safe_pdf_text(line)}) Tj"
        )

    commands.extend(
        (
            "ET",
            "BT",
            "/F1 8 Tf",
            "50 25 Td",
            (
                f"(Page {page_number} "
                f"of {page_count}) Tj"
            ),
            "ET",
        )
    )

    return "\n".join(
        commands
    ).encode(
        "latin-1",
        errors="replace",
    )


def _build_pdf(
    pages: tuple[
        tuple[str, ...],
        ...,
    ],
) -> bytes:
    objects: list[bytes] = []

    page_count = len(
        pages
    )

    catalog_object = 1
    pages_object = 2
    font_object = 3

    first_page_object = 4

    page_object_numbers: list[int] = []
    content_object_numbers: list[int] = []

    next_object = first_page_object

    for _ in pages:
        page_object_numbers.append(
            next_object
        )
        content_object_numbers.append(
            next_object + 1
        )
        next_object += 2

    objects.append(
        (
            f"<< /Type /Catalog "
            f"/Pages {pages_object} 0 R >>"
        ).encode(
            "ascii"
        )
    )

    kids = " ".join(
        f"{object_number} 0 R"
        for object_number
        in page_object_numbers
    )

    objects.append(
        (
            f"<< /Type /Pages "
            f"/Kids [{kids}] "
            f"/Count {page_count} >>"
        ).encode(
            "ascii"
        )
    )

    objects.append(
        (
            "<< /Type /Font "
            "/Subtype /Type1 "
            "/BaseFont /Helvetica >>"
        ).encode(
            "ascii"
        )
    )

    for index, page_lines in enumerate(
        pages,
        start=1,
    ):
        content = _pdf_stream_for_page(
            page_lines,
            page_number=index,
            page_count=page_count,
        )

        page_object_number = (
            page_object_numbers[
                index - 1
            ]
        )

        content_object_number = (
            content_object_numbers[
                index - 1
            ]
        )

        expected_page_number = (
            len(
                objects
            )
            + 1
        )

        if (
            expected_page_number
            != page_object_number
        ):
            raise ExecutivePredictiveReportPDFError(
                "Internal PDF object ordering failed"
            )

        objects.append(
            (
                f"<< /Type /Page "
                f"/Parent {pages_object} 0 R "
                "/MediaBox [0 0 595 842] "
                f"/Resources << /Font "
                f"<< /F1 {font_object} 0 R >> >> "
                f"/Contents {content_object_number} 0 R "
                ">>"
            ).encode(
                "ascii"
            )
        )

        objects.append(
            (
                f"<< /Length {len(content)} >>\n"
                "stream\n"
            ).encode(
                "ascii"
            )
            + content
            + b"\nendstream"
        )

    output = bytearray(
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    )

    offsets = [
        0
    ]

    for object_number, object_body in enumerate(
        objects,
        start=1,
    ):
        offsets.append(
            len(
                output
            )
        )

        output.extend(
            (
                f"{object_number} 0 obj\n"
            ).encode(
                "ascii"
            )
        )

        output.extend(
            object_body
        )

        output.extend(
            b"\nendobj\n"
        )

    xref_offset = len(
        output
    )

    output.extend(
        (
            f"xref\n0 {len(objects) + 1}\n"
        ).encode(
            "ascii"
        )
    )

    output.extend(
        b"0000000000 65535 f \n"
    )

    for offset in offsets[1:]:
        output.extend(
            (
                f"{offset:010d} "
                "00000 n \n"
            ).encode(
                "ascii"
            )
        )

    output.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} "
            f"/Root {catalog_object} 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode(
            "ascii"
        )
    )

    return bytes(
        output
    )


def _sanitize_file_name(
    value: str,
) -> str:
    normalized = "".join(
        character
        if (
            character.isalnum()
            or character
            in {
                "-",
                "_",
                ".",
            }
        )
        else "-"
        for character in str(
            value
        ).strip()
    )

    normalized = normalized.strip(
        ".-"
    )

    if not normalized:
        normalized = (
            "executive-predictive-report"
        )

    if not normalized.lower().endswith(
        ".pdf"
    ):
        normalized = (
            f"{normalized}.pdf"
        )

    return normalized


class ExecutivePredictiveReportPDFRenderer:
    def render_bytes(
        self,
        *,
        record: ExecutivePredictiveReportRecord,
        exported_at: datetime | None = None,
    ) -> tuple[
        bytes,
        int,
        datetime,
    ]:
        if not isinstance(
            record,
            ExecutivePredictiveReportRecord,
        ):
            raise TypeError(
                "record must be an "
                "ExecutivePredictiveReportRecord"
            )

        if not record.verify_hash():
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Source report record hash is invalid"
            )

        if not record.validation_valid:
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Source report validation is invalid"
            )

        if not record.source_audit_valid:
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Source audit is invalid"
            )

        resolved_exported_at = (
            _normalize_datetime(
                exported_at,
                field_name="exported_at",
            )
        )

        stored_at = datetime.fromisoformat(
            record.stored_at
        )

        if (
            stored_at.tzinfo is None
            or stored_at.utcoffset() is None
        ):
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Stored record timestamp is invalid"
            )

        if (
            resolved_exported_at
            < stored_at.astimezone(
                timezone.utc
            )
        ):
            raise ExecutivePredictiveReportPDFIntegrityError(
                "exported_at must not be earlier "
                "than stored_at"
            )

        lines = _build_report_lines(
            record,
            resolved_exported_at,
        )

        pages = _paginate(
            lines
        )

        pdf_bytes = _build_pdf(
            pages
        )

        if not pdf_bytes.startswith(
            b"%PDF-1.4"
        ):
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Generated content is not a PDF"
            )

        if not pdf_bytes.rstrip().endswith(
            b"%%EOF"
        ):
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Generated PDF is incomplete"
            )

        return (
            pdf_bytes,
            len(
                pages
            ),
            resolved_exported_at,
        )

    def export(
        self,
        *,
        store: ExecutivePredictiveReportStore,
        report_id: str,
        output_path: str | Path,
        exported_at: datetime | None = None,
        overwrite: bool = False,
    ) -> ExecutivePredictiveReportPDFExport:
        if not isinstance(
            store,
            ExecutivePredictiveReportStore,
        ):
            raise TypeError(
                "store must be an "
                "ExecutivePredictiveReportStore"
            )

        normalized_report_id = str(
            report_id
        ).strip()

        if not normalized_report_id:
            raise ValueError(
                "report_id must not be empty"
            )

        if not isinstance(
            overwrite,
            bool,
        ):
            raise TypeError(
                "overwrite must be a bool"
            )

        if not store.verify_chain():
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Executive report store chain is invalid"
            )

        record = store.get(
            normalized_report_id
        )

        if record is None:
            raise ExecutivePredictiveReportPDFError(
                "Executive predictive report "
                "was not found"
            )

        resolved_path = Path(
            output_path
        )

        if resolved_path.exists():
            if resolved_path.is_dir():
                resolved_path = (
                    resolved_path
                    / _sanitize_file_name(
                        record.report_id
                    )
                )

            elif not overwrite:
                raise ExecutivePredictiveReportPDFExistsError(
                    "Output PDF already exists"
                )

        elif (
            not resolved_path.suffix
            or resolved_path.suffix.lower()
            != ".pdf"
        ):
            resolved_path = (
                resolved_path
                / _sanitize_file_name(
                    record.report_id
                )
            )

        resolved_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if (
            resolved_path.exists()
            and not overwrite
        ):
            raise ExecutivePredictiveReportPDFExistsError(
                "Output PDF already exists"
            )

        (
            pdf_bytes,
            page_count,
            resolved_exported_at,
        ) = self.render_bytes(
            record=record,
            exported_at=exported_at,
        )

        temporary_file: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=(
                    f".{resolved_path.name}."
                ),
                suffix=".tmp",
                dir=resolved_path.parent,
                delete=False,
            ) as handle:
                temporary_file = handle.name
                handle.write(
                    pdf_bytes
                )
                handle.flush()
                os.fsync(
                    handle.fileno()
                )

            os.replace(
                temporary_file,
                resolved_path,
            )

            temporary_file = None

        finally:
            if (
                temporary_file is not None
                and os.path.exists(
                    temporary_file
                )
            ):
                os.unlink(
                    temporary_file
                )

        stored_bytes = (
            resolved_path.read_bytes()
        )

        if stored_bytes != pdf_bytes:
            raise ExecutivePredictiveReportPDFIntegrityError(
                "Exported PDF content verification failed"
            )

        pdf_sha256 = hashlib.sha256(
            stored_bytes
        ).hexdigest()

        return ExecutivePredictiveReportPDFExport(
            report_id=(
                record.report_id
            ),
            report_fingerprint=(
                record.report_fingerprint
            ),
            source_record_hash=(
                record.record_hash
            ),
            output_path=str(
                resolved_path.resolve()
            ),
            file_name=(
                resolved_path.name
            ),
            content_type=(
                "application/pdf"
            ),
            file_size_bytes=len(
                stored_bytes
            ),
            page_count=(
                page_count
            ),
            pdf_sha256=(
                pdf_sha256
            ),
            exported_at=(
                resolved_exported_at
            ),
            renderer_name=(
                PDF_SERVICE_NAME
            ),
            renderer_version=(
                PDF_SERVICE_VERSION
            ),
        )


def export_executive_predictive_report_pdf(
    *,
    store: ExecutivePredictiveReportStore,
    report_id: str,
    output_path: str | Path,
    exported_at: datetime | None = None,
    overwrite: bool = False,
) -> ExecutivePredictiveReportPDFExport:
    return (
        ExecutivePredictiveReportPDFRenderer()
        .export(
            store=store,
            report_id=report_id,
            output_path=output_path,
            exported_at=exported_at,
            overwrite=overwrite,
        )
    )
