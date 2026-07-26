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


def clean_model_markdown(text: Any) -> str:
    """
    Nettoie les marqueurs de présentation ajoutés par le modèle.

    Le contenu sera ensuite échappé avant son insertion dans le HTML.
    Les balises b et strong ne peuvent donc plus apparaître comme du
    texte visible sur le site.
    """
    cleaned = str(text or "").strip()

    cleaned = re.sub(
        r"</?\s*(?:b|strong)\s*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"&lt;/?\s*(?:b|strong)\s*&gt;",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"&amp;lt;/?\s*(?:b|strong)\s*&amp;gt;",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    if (
        cleaned.startswith("**")
        and cleaned.endswith("**")
    ):
        cleaned = cleaned[2:-2].strip()

    if (
        cleaned.startswith("__")
        and cleaned.endswith("__")
    ):
        cleaned = cleaned[2:-2].strip()

    cleaned = re.sub(
        r"^\s*\*{2}",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"\*{2}\s*$",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"^\s*_{2}",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"_{2}\s*$",
        "",
        cleaned,
    )

    return cleaned.strip()


def _study_payload(
    value: Any,
) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value

    to_dict = getattr(
        value,
        "to_dict",
        None,
    )

    if callable(to_dict):
        payload = to_dict()

        if isinstance(payload, dict):
            return payload

    return None


def _render_paragraphs(
    value: Any,
    css_class: str,
) -> str:
    cleaned = clean_model_markdown(value)

    if not cleaned:
        return ""

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(
            r"\n\s*\n",
            cleaned,
        )
        if paragraph.strip()
    ]

    rendered: list[str] = []

    for paragraph in paragraphs:
        safe_paragraph = html.escape(
            paragraph
        ).replace(
            "\n",
            "<br>",
        )

        rendered.append(
            f'  <p class="{css_class}">'
            f"{safe_paragraph}"
            "</p>"
        )

    return "\n".join(rendered)


def _commentary_label(key: str) -> str:
    return COMMENTARY_LABELS.get(
        key,
        (
            key
            .replace("_", " ")
            .replace("-", " ")
            .title()
        ),
    )


def _commentary_keys(
    commentaries: dict[str, Any],
) -> list[str]:
    ordered = [
        key
        for key in COMMENTARY_ORDER
        if key in commentaries
    ]

    ordered.extend(
        sorted(
            key
            for key in commentaries
            if key not in COMMENTARY_ORDER
        )
    )

    return ordered


def _commentary_summary(entry: Any) -> str:
    if isinstance(entry, str):
        return clean_model_markdown(entry)

    if not isinstance(entry, dict):
        return ""

    return clean_model_markdown(
        entry.get("summary")
        or entry.get("resume")
        or entry.get("text")
    )


def _render_commentaries(
    commentaries: Any,
) -> str:
    if not isinstance(commentaries, dict):
        return ""

    blocks: list[str] = []

    for key in _commentary_keys(commentaries):
        summary = _commentary_summary(
            commentaries.get(key)
        )

        if not summary:
            continue

        safe_key = re.sub(
            r"[^a-z0-9_-]",
            "-",
            key.lower(),
        )

        blocks.extend(
            [
                (
                    '<section class="talmud-commentary '
                    f'talmud-commentary-{safe_key}">'
                ),
                (
                    "  <h4>"
                    f"{html.escape(_commentary_label(key))}"
                    "</h4>"
                ),
                _render_paragraphs(
                    summary,
                    "talmud-commentary-text",
                ),
                "</section>",
            ]
        )

    if not blocks:
        return ""

    return "\n".join(
        [
            (
                '<section class="talmud-study-section '
                'talmud-mefarshim-section">'
            ),
            "  <h3>Éclairage des méfarchim</h3>",
            *blocks,
            "</section>",
        ]
    )


def render_study_html(
    translation: Any,
    explanation: str | None = None,
    study: dict[str, Any] | Any | None = None,
) -> str:
    """
    Génère le HTML d’un segment TALMUD AI.

    Mode léger :
    - traduction française ;
    - éclairages concis des méfarchim pertinents.

    La signature historique reste acceptée afin de conserver la
    compatibilité avec les autres scripts V7.2.
    """
    direct_study = None

    if (
        explanation is None
        and study is None
    ):
        direct_study = _study_payload(
            translation
        )

    if direct_study is not None:
        study_payload = direct_study
        translation_text = (
            study_payload.get(
                "translation",
                "",
            )
        )
        explanation_text = (
            study_payload.get(
                "explanation",
                "",
            )
        )

    else:
        study_payload = _study_payload(
            study
        )
        translation_text = translation
        explanation_text = explanation or ""

    cleaned_translation = clean_model_markdown(
        translation_text
    )
    cleaned_explanation = clean_model_markdown(
        explanation_text
    )

    parts: list[str] = [
        (
            '<section class="talmud-study-block '
            'talmud-study-light">'
        ),
        (
            '<section class="talmud-study-section '
            'talmud-translation-section">'
        ),
        "  <h3>Traduction française</h3>",
        (
            '  <p class="talmud-translation">'
            f"{html.escape(cleaned_translation)}"
            "</p>"
        ),
        "</section>",
    ]

    # Les nouveaux résultats légers laissent explanation vide.
    # Cette section reste uniquement pour la compatibilité avec
    # d’anciens appels possédant encore une explication.
    if cleaned_explanation:
        parts.extend(
            [
                (
                    '<section class="talmud-study-section '
                    'talmud-explanation-section">'
                ),
                "  <h3>Étude détaillée</h3>",
                _render_paragraphs(
                    cleaned_explanation,
                    "talmud-explanation",
                ),
                "</section>",
            ]
        )

    if study_payload is not None:
        commentaries_html = (
            _render_commentaries(
                study_payload.get(
                    "commentaries"
                )
            )
        )

        if commentaries_html:
            parts.append(
                commentaries_html
            )

    parts.append("</section>")

    return "\n".join(
        part
        for part in parts
        if part
    )
