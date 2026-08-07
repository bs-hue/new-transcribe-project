"""Export registry.

Adding a format is: subclass ``Exporter``, add it to ``_EXPORTERS``. It shows up
in the API enum, the bulk export, and the UI dropdown with no other change.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from app.core.errors import ExportFormatError
from app.core.text import slugify_filename
from app.services.export.base import ExportDocument, Exporter, ExportSegment
from app.services.export.office import DocxExporter, XlsxExporter
from app.services.export.plain import (
    JsonExporter,
    MarkdownExporter,
    SrtExporter,
    TxtExporter,
    VttExporter,
)

_EXPORTERS: dict[str, Exporter] = {
    exporter.format: exporter
    for exporter in (
        TxtExporter(),
        DocxExporter(),
        MarkdownExporter(),
        XlsxExporter(),
        JsonExporter(),
        SrtExporter(),
        VttExporter(),
    )
}


def available_formats() -> list[dict[str, object]]:
    return [
        {
            "format": exporter.format,
            "display_name": exporter.display_name,
            "extension": exporter.extension,
            "content_type": exporter.content_type,
            "requires_segments": exporter.requires_segments,
            "combinable": exporter.combinable,
        }
        for exporter in _EXPORTERS.values()
    ]


def format_names() -> list[str]:
    return list(_EXPORTERS)


def get_exporter(format_name: str) -> Exporter:
    exporter = _EXPORTERS.get((format_name or "").strip().lower())
    if exporter is None:
        raise ExportFormatError(
            f"Unsupported export format {format_name!r}. "
            f"Supported: {', '.join(format_names())}."
        )
    return exporter


def export_one(document: ExportDocument, format_name: str) -> tuple[bytes, str, str]:
    """Render one transcript. Returns ``(content, filename, content_type)``."""
    exporter = get_exporter(format_name)
    if exporter.requires_segments and not document.segments:
        raise ExportFormatError(
            f"{exporter.display_name} export needs timed segments, and this "
            "transcript has none."
        )
    return exporter.render(document), exporter.filename(document), exporter.content_type


def export_many(
    documents: list[ExportDocument], format_name: str, *, combine: bool = True
) -> tuple[bytes, str, str]:
    """Render several transcripts.

    By default the formats people read — TXT, Markdown, DOCX — and the formats
    people tabulate — XLSX, JSON — all produce a single file, because a batch of
    reels is usually one piece of research rather than seven.

    ``combine=False`` asks for a ZIP of individual files instead, and subtitle
    formats produce one regardless. Names are de-duplicated so two videos with
    the same title do not overwrite each other.
    """
    exporter = get_exporter(format_name)
    if not documents:
        raise ExportFormatError("No transcripts matched the export request.")

    combined = exporter.render_many(documents) if combine else None
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if combined is not None:
        return combined, f"transcripts-{stamp}.{exporter.extension}", exporter.content_type

    usable = [
        doc for doc in documents if doc.segments or not exporter.requires_segments
    ]
    if not usable:
        raise ExportFormatError(
            f"None of the selected transcripts have the timed segments "
            f"{exporter.display_name} export requires."
        )

    buffer = io.BytesIO()
    seen: dict[str, int] = {}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for document in usable:
            stem = slugify_filename(document.safe_title)
            count = seen.get(stem, 0)
            seen[stem] = count + 1
            suffix = f"-{count}" if count else ""
            archive.writestr(
                f"{stem}{suffix}.{exporter.extension}", exporter.render(document)
            )

    return buffer.getvalue(), f"transcripts-{stamp}-{exporter.format}.zip", "application/zip"


__all__ = [
    "ExportDocument",
    "ExportSegment",
    "Exporter",
    "available_formats",
    "export_many",
    "export_one",
    "format_names",
    "get_exporter",
]
