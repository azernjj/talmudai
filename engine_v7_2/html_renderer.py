from __future__ import annotations

import html
import re
from typing import Any


COMMENTARY_LABELS = {
    "rachi": "Rachi",
    "tossefot": "Tossefot",
    "ritva": "Ritva",
    "rosh": "Roch",
    "pnei_yehoshoua": "Pnei Yehoshoua",
}


COMMENTARY_ORDER = (
    "rachi",
    "tossefot",
    "ritva",
    "rosh",
    "pnei_yehoshoua",
)


def clean_model_markdown(text: str) -> str:
    """
    Retire les marqueurs Markdown simples ajoutés par le modèle,
    sans modifier le contenu éditorial.
    """
    cleaned = str(text or "").strip()

    # Le modèle ajoute parfois des balises de mise en forme alors que
    # le rendu HTML applique lui-même le style nécessaire.
    cleaned = re.sub(
        r"</?\\s*(?:b|strong)\\s*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"&lt;/?\\s*(?:b|strong)\\s*&gt;",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    if cleaned.startswith("**") and cleaned.endswith("**"):
        cleaned = cleaned[2:-2].strip()

    if cleaned.startswith("__") and cleaned.endswith("__"):
        cleaned = cleaned[2:-2].strip()

    cleaned = re.sub(r"^\s*\*{2}", "", cleaned)
    cleaned = re.sub(r"\*{2}\s*$", "", cleaned)
    cleaned = re.sub(r"^\s*_{2}", "", cleaned)
    cleaned = re.sub(r"_{2}\s*$", "", cleaned)

    return cleaned.strip()


def _render_paragraphs(text: Any, css_class: str) -> str:
    cleaned = clean_model_markdown(str(text or ""))

    if not cleaned:
        return ""

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", cleaned)
        if paragraph.strip()
    ]

    rendered: list[str] = []

    for paragraph in paragraphs:
        safe_paragraph = html.escape(paragraph).replace("\n", "<br>")
        rendered.append(
            f'  <p class="{css_class}">{safe_paragraph}</p>'
        )

    return "\n".join(rendered)


def _render_string_list(
    title: str,
    values: Any,
    *,
    section_class: str,
    list_class: str,
) -> str:
    if not isinstance(values, list):
        return ""

    cleaned_values = [
        clean_model_markdown(str(value))
        for value in values
        if str(value or "").strip()
    ]

    if not cleaned_values:
        return ""

    items = "\n".join(
        f"    <li>{html.escape(value)}</li>"
        for value in cleaned_values
    )

    return (
        f'<section class="talmud-study-section {section_class}">\n'
        f"  <h3>{html.escape(title)}</h3>\n"
        f'  <ul class="{list_class}">\n'
        f"{items}\n"
        "  </ul>\n"
        "</section>"
    )


def _commentary_label(key: str) -> str:
    if key in COMMENTARY_LABELS:
        return COMMENTARY_LABELS[key]

    return key.replace("_", " ").replace("-", " ").title()


def _commentary_keys(commentaries: dict[str, Any]) -> list[str]:
    ordered = [
        key
        for key in COMMENTARY_ORDER
        if key in commentaries
    ]

    additional = sorted(
        key
        for key in commentaries
        if key not in COMMENTARY_ORDER
    )

    return ordered + additional


def _render_commentaries(commentaries: Any) -> str:
    """
    Affiche uniquement les commentaires réellement utilisés et résumés.

    Un commentaire disponible mais sans apport pertinent pour le segment
    reste enregistré dans le JSON, sans produire une section vide à l'écran.
    """
    if not isinstance(commentaries, dict):
        return ""

    blocks: list[str] = []

    for key in _commentary_keys(commentaries):
        entry = commentaries.get(key)

        if not isinstance(entry, dict):
            continue

        summary = clean_model_markdown(
            str(entry.get("summary", ""))
        )
        if not summary:
            continue

        summary_html = _render_paragraphs(
            summary,
            "talmud-commentary-text",
        )

        blocks.append(
            '<section class="talmud-study-section talmud-commentary '
            f'talmud-commentary-{html.escape(key)}">\n'
            f"  <h3>{html.escape(_commentary_label(key))}</h3>\n"
            f"{summary_html}\n"
            "</section>"
        )

    return "\n".join(blocks)


def _render_halakha(halakha: Any) -> str:
    if not isinstance(halakha, dict):
        return ""

    text = clean_model_markdown(str(halakha.get("text", "")))
    sources = halakha.get("sources", [])
    available = halakha.get("available") is True

    if not available or not text:
        return ""

    parts = [
        '<section class="talmud-study-section talmud-halakha">',
        "  <h3>Halakha</h3>",
        _render_paragraphs(text, "talmud-halakha-text"),
    ]

    if isinstance(sources, list):
        cleaned_sources = [
            clean_model_markdown(str(source))
            for source in sources
            if str(source or "").strip()
        ]

        if cleaned_sources:
            source_items = ", ".join(
                html.escape(source)
                for source in cleaned_sources
            )
            parts.append(
                '  <p class="talmud-halakhic-sources">'
                f"<strong>Sources :</strong> {source_items}</p>"
            )

    parts.append("</section>")
    return "\n".join(parts)


def _render_glossary(glossary: Any) -> str:
    if not isinstance(glossary, list):
        return ""

    rows: list[str] = []

    for entry in glossary:
        if not isinstance(entry, dict):
            continue

        source = clean_model_markdown(str(entry.get("source", "")))
        french = clean_model_markdown(str(entry.get("french", "")))
        note = clean_model_markdown(str(entry.get("note", "")))

        if not source or not french:
            continue

        note_html = ""
        if note:
            note_html = (
                ' <span class="talmud-glossary-note">'
                f"— {html.escape(note)}</span>"
            )

        rows.append(
            "    <li>"
            f'<span class="talmud-glossary-source">'
            f"{html.escape(source)}</span>"
            " : "
            f'<span class="talmud-glossary-french">'
            f"{html.escape(french)}</span>"
            f"{note_html}"
            "</li>"
        )

    if not rows:
        return ""

    return (
        '<section class="talmud-study-section talmud-glossary">\n'
        "  <h3>Glossaire</h3>\n"
        '  <ul class="talmud-glossary-list">\n'
        + "\n".join(rows)
        + "\n  </ul>\n"
        "</section>"
    )


def _study_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return payload

    return None


def render_study_html(
    translation: Any,
    explanation: str | None = None,
    study: dict[str, Any] | Any | None = None,
) -> str:
    """
    Génère le HTML linéaire complet d'un segment d'étude.

    Formats acceptés :
    - render_study_html(study_block)
    - render_study_html(translation, explanation)
    - render_study_html(translation, explanation, study)
    """
    direct_study = None

    if explanation is None and study is None:
        direct_study = _study_payload(translation)

    if direct_study is not None:
        study_payload = direct_study
        translation_text = study_payload.get("translation", "")
        explanation_text = study_payload.get("explanation", "")
    else:
        study_payload = _study_payload(study)
        translation_text = translation
        explanation_text = explanation or ""

    cleaned_translation = clean_model_markdown(
        str(translation_text or "")
    )
    cleaned_explanation = clean_model_markdown(
        str(explanation_text or "")
    )

    parts: list[str] = [
        '<section class="talmud-study-block">',
        (
            '<section class="talmud-study-section '
            'talmud-translation-section">'
        ),
        "  <h3>Traduction française</h3>",
        (
            '  <p class="talmud-translation"><strong>'
            f"{html.escape(cleaned_translation)}"
            "</strong></p>"
        ),
        "  </section>",
        (
            '<section class="talmud-study-section '
            'talmud-explanation-section">'
        ),
        "  <h3>Étude détaillée</h3>",
        _render_paragraphs(
            cleaned_explanation,
            "talmud-explanation",
        ),
        "  </section>",
    ]

    if study_payload is not None:
        commentaries_html = _render_commentaries(
            study_payload.get("commentaries")
        )
        if commentaries_html:
            parts.append(commentaries_html)

        halakha_html = _render_halakha(
            study_payload.get("halakha")
        )
        if halakha_html:
            parts.append(halakha_html)

        applications_html = _render_string_list(
            "Applications pratiques",
            study_payload.get("applications"),
            section_class="talmud-applications",
            list_class="talmud-applications-list",
        )
        if applications_html:
            parts.append(applications_html)

        glossary_html = _render_glossary(
            study_payload.get("glossary")
        )
        if glossary_html:
            parts.append(glossary_html)

        summary = clean_model_markdown(
            str(study_payload.get("summary", ""))
        )
        if summary:
            parts.extend(
                [
                    (
                        '<section class="talmud-study-section '
                        'talmud-summary">'
                    ),
                    "  <h3>Résumé</h3>",
                    _render_paragraphs(
                        summary,
                        "talmud-summary-text",
                    ),
                    "</section>",
                ]
            )

        key_points_html = _render_string_list(
            "Points clés",
            study_payload.get("key_points"),
            section_class="talmud-key-points",
            list_class="talmud-key-points-list",
        )
        if key_points_html:
            parts.append(key_points_html)

        references_html = _render_string_list(
            "Références",
            study_payload.get("references"),
            section_class="talmud-references",
            list_class="talmud-references-list",
        )
        if references_html:
            parts.append(references_html)

    parts.append("</section>")

    return "\n".join(part for part in parts if part)
