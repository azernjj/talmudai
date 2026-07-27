from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from .aligned_commentaries import AlignedCommentary
from .aligned_prompts import (
    SYSTEM_INSTRUCTIONS,
    build_aligned_input,
)
from .english_source import EnglishSegmentSource
from .openai_client import ModelResult, ResponsesJsonClient


HTML_PATTERN = re.compile(
    r"</?[a-zA-Z][^>]*>",
    flags=re.IGNORECASE,
)

HEBREW_PATTERN = re.compile(
    r"[\u0590-\u05FF]",
)


@dataclass
class AlignedTranslationRun:
    translation_fr: str
    commentaries: dict[str, dict[str, Any]]
    confidence: float
    api: ModelResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "translation_fr": self.translation_fr,
            "commentaries": self.commentaries,
            "confidence": self.confidence,
        }


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = html.unescape(text)
    text = HTML_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalise_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, confidence))


def _contains_too_much_hebrew(text: str) -> bool:
    """
    Autorise un terme hébreu isolé, mais refuse un résumé qui serait
    essentiellement resté en hébreu.
    """
    hebrew_characters = HEBREW_PATTERN.findall(text)

    if len(hebrew_characters) < 12:
        return False

    visible_characters = [
        character
        for character in text
        if not character.isspace()
    ]

    if not visible_characters:
        return False

    ratio = len(hebrew_characters) / len(visible_characters)
    return ratio >= 0.12


def _normalise_commentaries(
    value: Any,
    available: dict[str, list[AlignedCommentary]],
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        value = {}

    result: dict[str, dict[str, Any]] = {}

    for key in ("rachi", "tossefot"):
        entries = available.get(key, [])

        if not entries:
            continue

        raw_entry = value.get(key, {})

        if isinstance(raw_entry, str):
            summary = _clean_text(raw_entry)
        elif isinstance(raw_entry, dict):
            summary = _clean_text(
                raw_entry.get("summary")
            )
        else:
            summary = ""

        if not summary:
            raise ValueError(
                f"Le résumé français de {key} est vide."
            )

        if _contains_too_much_hebrew(summary):
            raise ValueError(
                f"Le résumé de {key} contient trop de texte "
                "hébreu non traduit."
            )

        result[key] = {
            "available": True,
            "source_used": True,
            "summary": summary,
            "refs": [
                entry.ref
                for entry in entries
            ],
            "full_translation_fr": "",
        }

    return result


class AlignedTranslator:
    """
    Traducteur économique du corpus aligné.

    Un seul appel produit :
    - la traduction française du segment anglais aligné ;
    - un résumé français de Rachi lorsqu'il existe ;
    - un résumé français de Tossefot lorsqu'il existe.

    Aucun relecteur n'est appelé.
    """

    def __init__(
        self,
        client: ResponsesJsonClient,
        model: str = "gpt-5-mini",
        max_output_tokens: int = 1400,
    ) -> None:
        self.client = client
        self.model = model
        self.max_output_tokens = max_output_tokens

    def translate(
        self,
        source: EnglishSegmentSource,
        commentaries: dict[str, list[AlignedCommentary]],
    ) -> AlignedTranslationRun:
        if not source.english.strip():
            raise ValueError(
                f"Aucun texte anglais aligné pour "
                f"{source.base_ref}."
            )

        input_text = build_aligned_input(
            source,
            commentaries,
        )

        result = self.client.create_json(
            model=self.model,
            instructions=SYSTEM_INSTRUCTIONS,
            input_text=input_text,
            max_output_tokens=self.max_output_tokens,
        )

        data = result.data

        if not isinstance(data, dict):
            raise TypeError(
                "Le modèle doit renvoyer un objet JSON."
            )

        translation = _clean_text(
            data.get("translation_fr")
            or data.get("translation")
        )

        if not translation:
            raise ValueError(
                "La traduction française est vide."
            )

        if HTML_PATTERN.search(translation):
            raise ValueError(
                "La traduction contient encore une balise HTML."
            )

        if _contains_too_much_hebrew(translation):
            raise ValueError(
                "La traduction contient trop de texte hébreu "
                "non traduit."
            )

        normalised_commentaries = _normalise_commentaries(
            data.get("commentaries"),
            commentaries,
        )

        return AlignedTranslationRun(
            translation_fr=translation,
            commentaries=normalised_commentaries,
            confidence=_normalise_confidence(
                data.get("confidence")
            ),
            api=result,
        )
