from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .aligned_translator import AlignedTranslationRun
from .english_source import EnglishSegmentSource


COMMENTARY_LABELS = {
    "rachi": "Rachi",
    "tossefot": "Tossefot",
}


def _paragraph(text: str, css_class: str) -> str:
    safe = html.escape(str(text or "").strip())
    return f'  <p class="{css_class}">{safe}</p>'


def render_aligned_html(
    translation_fr: str,
    commentaries: dict[str, dict[str, Any]],
) -> str:
    parts = [
        '<section class="talmud-study-block talmud-study-aligned">',
        '<section class="talmud-study-section talmud-translation-section">',
        '  <h3>Traduction française</h3>',
        _paragraph(
            translation_fr,
            "talmud-translation",
        ),
        "</section>",
    ]

    commentary_blocks: list[str] = []

    for key in ("rachi", "tossefot"):
        entry = commentaries.get(key, {})

        if not isinstance(entry, dict):
            continue

        summary = str(
            entry.get("summary") or ""
        ).strip()

        if not summary:
            continue

        label = COMMENTARY_LABELS[key]

        commentary_blocks.extend(
            [
                (
                    '<section class="talmud-commentary '
                    f'talmud-commentary-{key}">'
                ),
                f"  <h4>{label}</h4>",
                _paragraph(
                    summary,
                    "talmud-commentary-text",
                ),
                "</section>",
            ]
        )

    if commentary_blocks:
        parts.extend(
            [
                '<section class="talmud-study-section '
                'talmud-mefarshim-section">',
                "  <h3>Éclairage des méfarchim</h3>",
                *commentary_blocks,
                "</section>",
            ]
        )

    parts.append("</section>")
    return "\n".join(parts)


def _empty_commentary() -> dict[str, Any]:
    return {
        "available": False,
        "source_used": False,
        "summary": "",
        "refs": [],
        "full_translation_fr": "",
    }


def build_study(
    run: AlignedTranslationRun,
) -> dict[str, Any]:
    commentaries = {
        "rachi": _empty_commentary(),
        "tossefot": _empty_commentary(),
    }

    for key in ("rachi", "tossefot"):
        entry = run.commentaries.get(key)

        if isinstance(entry, dict):
            commentaries[key] = dict(entry)

    return {
        "translation": run.translation_fr,
        "explanation": "",
        "commentaries": commentaries,
        "halakha": {
            "available": False,
            "text": "",
            "sources": [],
        },
        "applications": [],
        "glossary": [],
        "summary": "",
        "key_points": [],
        "references": [],
        "confidence": run.confidence,
        "issues": [],
        "review_note": "",
    }


def apply_aligned_translation(
    segment: dict[str, Any],
    source: EnglishSegmentSource,
    run: AlignedTranslationRun,
    *,
    model: str,
    cost: dict[str, Any] | None = None,
) -> None:
    """
    Remplace uniquement les champs français et éditoriaux du segment.

    Les champs hébreu et anglais ne sont jamais modifiés.
    """
    if not isinstance(segment, dict):
        raise TypeError(
            "Le segment cible doit être un dictionnaire."
        )

    study = build_study(run)

    segment["fr"] = run.translation_fr
    segment["fr_explanation"] = ""
    segment["fr_html"] = render_aligned_html(
        run.translation_fr,
        study["commentaries"],
    )

    segment["translation_meta"] = {
        "engine": "talmud-ai-aligned-v7.2",
        "source": "aligned_english",
        "model": model,
        "base_ref": source.base_ref,
    }

    used = [
        key
        for key, entry in study["commentaries"].items()
        if entry.get("source_used") is True
    ]

    available = [
        key
        for key, entry in study["commentaries"].items()
        if entry.get("available") is True
    ]

    segment["fr_editorial"] = {
        "engine_version": "7.2-aligned",
        "schema_version": "study-aligned-v7.2",
        "mode": "aligned-translation",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "masechet": source.masechet,
        "daf": source.daf,
        "segment_number": source.segment_number,
        "translator_model": model,
        "reviewer_model": None,
        "reviewer_used": False,
        "translator_response_id": run.api.response_id,
        "commentaries_available": available,
        "commentaries_used": used,
        "tokens": {
            "input": run.api.input_tokens,
            "output": run.api.output_tokens,
            "total": run.api.total_tokens,
        },
        "cost": dict(cost or {}),
    }

    segment["study"] = study


def save_document_atomic(
    path: str | Path,
    document: dict[str, Any],
) -> Path:
    target = Path(path).resolve()
    temporary = target.with_name(
        target.name + ".writing"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            document,
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(temporary, target)
    return target
