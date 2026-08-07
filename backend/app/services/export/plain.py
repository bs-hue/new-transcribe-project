"""Text-based exporters: TXT, Markdown, SRT, VTT, JSON."""

from __future__ import annotations

import json
import textwrap

from app.core.text import format_duration, format_timestamp
from app.services.export.base import ExportDocument, Exporter


def _header_lines(document: ExportDocument) -> list[str]:
    lines = [document.safe_title]
    if document.author:
        lines.append(f"Creator: {document.author}")
    lines.append(f"Platform: {document.platform}")
    lines.append(f"Source: {document.source_url}")
    if document.duration_seconds:
        lines.append(f"Duration: {format_duration(document.duration_seconds)}")
    if document.language:
        lines.append(f"Language: {document.language}")
    lines.append(f"Words: {document.word_count}")
    return lines


class TxtExporter(Exporter):
    format = "txt"
    extension = "txt"
    content_type = "text/plain; charset=utf-8"
    display_name = "Plain text"
    combinable = True

    def render(self, document: ExportDocument) -> bytes:
        header = _header_lines(document)
        body = "\n".join(textwrap.wrap(document.text, width=100)) or "(no speech detected)"
        content = "\n".join([*header, "=" * 60, "", body, ""])
        return content.encode("utf-8")

    def render_many(self, documents: list[ExportDocument]) -> bytes:
        # A researcher reading seven reels wants one script to scroll, not seven
        # files to open in turn. The contents list keeps that scroll navigable.
        parts = [
            f"COMBINED TRANSCRIPTS — {len(documents)} videos",
            "=" * 60,
            "",
            "CONTENTS",
        ]
        parts += [
            f"{number:>3}. {doc.safe_title}"
            for number, doc in enumerate(documents, start=1)
        ]

        for number, document in enumerate(documents, start=1):
            body = (
                "\n".join(textwrap.wrap(document.text, width=100))
                or "(no speech detected)"
            )
            parts += [
                "",
                "#" * 60,
                f"{number}. {document.safe_title}",
                *_header_lines(document)[1:],
                "-" * 60,
                "",
                body,
            ]

        return "\n".join([*parts, ""]).encode("utf-8")


class MarkdownExporter(Exporter):
    format = "md"
    extension = "md"
    content_type = "text/markdown; charset=utf-8"
    display_name = "Markdown"
    combinable = True

    def render(self, document: ExportDocument) -> bytes:
        parts = [f"# {document.safe_title}", ""]

        meta = [
            ("Creator", document.author),
            ("Platform", document.platform),
            ("Duration", format_duration(document.duration_seconds)),
            ("Language", document.language),
            ("Words", str(document.word_count)),
            ("Source", f"[{document.source_url}]({document.source_url})"),
        ]
        parts += ["| Field | Value |", "| --- | --- |"]
        parts += [f"| {label} | {value} |" for label, value in meta if value]
        parts += ["", "## Transcript", "", document.text or "_(no speech detected)_", ""]

        if document.segments:
            parts += ["## Timed segments", ""]
            parts += [
                f"**[{format_timestamp(s.start, separator='.')[:-4]}]** {s.text}"
                for s in document.segments
            ]
            parts.append("")

        return "\n".join(parts).encode("utf-8")

    def _section(self, number: int, document: ExportDocument) -> list[str]:
        """One transcript, demoted a heading level to sit under the contents."""
        meta = [
            ("Creator", document.author),
            ("Platform", document.platform),
            ("Duration", format_duration(document.duration_seconds)),
            ("Language", document.language),
            ("Words", str(document.word_count)),
            ("Source", f"[{document.source_url}]({document.source_url})"),
        ]
        return [
            f"## {number}. {document.safe_title}",
            "",
            "| Field | Value |",
            "| --- | --- |",
            *[f"| {label} | {value} |" for label, value in meta if value],
            "",
            document.text or "_(no speech detected)_",
            "",
            "---",
            "",
        ]

    def render_many(self, documents: list[ExportDocument]) -> bytes:
        # Timed segments are deliberately dropped here. Seven segment tables in
        # one document buries the thing the combined file exists to show — the
        # scripts, read end to end. Export a single transcript for the detail.
        parts = [
            "# Combined transcripts",
            "",
            f"{len(documents)} videos.",
            "",
            "## Contents",
            "",
            *[
                f"{number}. {doc.safe_title}"
                for number, doc in enumerate(documents, start=1)
            ],
            "",
            "---",
            "",
        ]
        for number, document in enumerate(documents, start=1):
            parts += self._section(number, document)
        return "\n".join(parts).encode("utf-8")


class JsonExporter(Exporter):
    format = "json"
    extension = "json"
    content_type = "application/json"
    display_name = "JSON"
    combinable = True

    def _payload(self, document: ExportDocument) -> dict:
        return {
            "transcript_id": document.transcript_id,
            "video_id": document.video_id,
            "title": document.safe_title,
            "author": document.author,
            "platform": document.platform,
            "source_url": document.source_url,
            "duration_seconds": document.duration_seconds,
            "language": document.language,
            "provider": document.provider,
            "model": document.model,
            "word_count": document.word_count,
            "published_at": document.published_at.isoformat() if document.published_at else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "text": document.text,
            "segments": [
                {
                    "index": s.index,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "speaker": s.speaker,
                }
                for s in document.segments
            ],
        }

    def render(self, document: ExportDocument) -> bytes:
        return json.dumps(self._payload(document), indent=2, ensure_ascii=False).encode("utf-8")

    def render_many(self, documents: list[ExportDocument]) -> bytes:
        payload = {
            "count": len(documents),
            "transcripts": [self._payload(doc) for doc in documents],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


class SrtExporter(Exporter):
    format = "srt"
    extension = "srt"
    content_type = "application/x-subrip"
    display_name = "SubRip (SRT)"
    requires_segments = True

    def render(self, document: ExportDocument) -> bytes:
        blocks = []
        for number, segment in enumerate(document.segments, start=1):
            start = format_timestamp(segment.start, separator=",")
            end = format_timestamp(segment.end, separator=",")
            blocks.append(f"{number}\n{start} --> {end}\n{segment.text}\n")
        return ("\n".join(blocks) or "").encode("utf-8")


class VttExporter(Exporter):
    format = "vtt"
    extension = "vtt"
    content_type = "text/vtt; charset=utf-8"
    display_name = "WebVTT"
    requires_segments = True

    def render(self, document: ExportDocument) -> bytes:
        blocks = ["WEBVTT", ""]
        for number, segment in enumerate(document.segments, start=1):
            start = format_timestamp(segment.start, separator=".")
            end = format_timestamp(segment.end, separator=".")
            blocks.append(f"{number}\n{start} --> {end}\n{segment.text}\n")
        return "\n".join(blocks).encode("utf-8")
