from __future__ import annotations

import html
import json
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


EXACT_TRANSLATION_INSTRUCTIONS = """Traduis directement
hebrew_aramaic de l’hébreu/araméen talmudique en français.

RÈGLES
- hebrew_aramaic est l’unique texte à traduire.
- semantic_aid_english sert seulement à désambiguïser.
- N’ajoute aucune explication provenant de l’anglais.
- Pour un fragment elliptique, rétablis seulement entre crochets
  le mot indispensable.
- Respecte questions, négations, raisonnements et noms propres.
- Produis un français fidèle, naturel et concis.
- כהן=Cohen ; כהנים=Cohanim ; תרומה=terouma.
- משמרה ou אשמורה=garde, jamais veille.
- מזיקין=démons ; מפולת=effondrement ; חשד=soupçon.
- חורבה=ruine ; דברא=champ ; כשרי=intègres ;
  פריצי=dépravés.
- קשיא ד... אד... signifie que deux enseignements se contredisent.
- תרי תנאי אליבא ד... : deux Tannaïm rapportent différemment
  l’opinion de...
- תא שמע=viens et écoute ; שמע מינה=on en déduit.
- ואיבעית אימא=et si tu veux, dis plutôt.
- ותיפוק ליה=et qu’on le déduise plutôt de...
- תיקו=Teikou.
- N’utilise jamais prêtre ou sacrificateur.
- Aucun HTML ni Markdown.

Retourne uniquement :
{"translation_fr":"traduction exacte","confidence":0.0}
"""

FORBIDDEN_COHEN_TRANSLATIONS = re.compile(
    r"\b(?:prêtre|prêtres|sacrificateur|sacrificateurs)\b",
    flags=re.IGNORECASE,
)


@dataclass
class AlignedTranslationRun:
    translation_fr: str
    explanation_fr: str
    commentaries: dict[str, dict[str, Any]]
    confidence: float
    api: ModelResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "translation_fr": self.translation_fr,
            "explanation_fr": self.explanation_fr,
            "commentaries": self.commentaries,
            "confidence": self.confidence,
        }


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = html.unescape(text)
    text = HTML_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_hebrew_marks(value: str) -> str:
    """
    Supprime les signes massorétiques afin de reconnaître les
    formules talmudiques indépendamment de la vocalisation.
    """
    return re.sub(
        r"[\u0591-\u05C7]",
        "",
        str(value or ""),
    )


def _normalise_exact_formula(
    hebrew: str,
    translation: str,
) -> str:
    """
    Corrige de manière déterministe certaines formules
    talmudiques que le modèle traduit parfois littéralement.
    """
    source = _strip_hebrew_marks(hebrew)
    source = re.sub(r"\s+", " ", source).strip()

    contradiction = re.fullmatch(
        r"קשיא דרבי (.+?) אדרבי \1[!！]?",
        source,
    )

    if contradiction:
        sage_match = re.search(
            r"Rabbi\s+([^!—,:;?]+)",
            translation,
            flags=re.IGNORECASE,
        )

        if sage_match:
            sage = sage_match.group(1).strip()

            return (
                f"L’enseignement de Rabbi {sage} contredit "
                f"un autre enseignement de Rabbi {sage} !"
            )

    return translation


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
    - la traduction française exacte du segment hébreu/araméen ;
    - l'explication française issue de l'anglais aligné ;
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
        *,
        exact_only: bool = False,
    ) -> AlignedTranslationRun:
        if not source.hebrew.strip():
            raise ValueError(
                f"Aucun texte hébreu/araméen pour "
                f"{source.base_ref}."
            )

        if exact_only:
            input_text = (
                "SEGMENT À TRADUIRE\n"
                + json.dumps(
                    {
                        "reference": source.base_ref,
                        "hebrew_aramaic": source.hebrew,
                        "semantic_aid_english": (
                            source.english
                        ),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            instructions = EXACT_TRANSLATION_INSTRUCTIONS
            output_limit = min(
                self.max_output_tokens,
                600,
            )
        else:
            input_text = build_aligned_input(
                source,
                commentaries,
            )
            instructions = SYSTEM_INSTRUCTIONS
            output_limit = self.max_output_tokens

        result = self.client.create_json(
            model=self.model,
            instructions=instructions,
            input_text=input_text,
            max_output_tokens=output_limit,
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

        if exact_only:
            translation = _normalise_exact_formula(
                source.hebrew,
                translation,
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

        if FORBIDDEN_COHEN_TRANSLATIONS.search(translation):
            raise ValueError(
                "La traduction emploie prêtre ou sacrificateur "
                "au lieu de Cohen/Cohanim."
            )

        explanation = (
            ""
            if exact_only
            else _clean_text(
                data.get("explanation_fr")
                or data.get("explanation")
            )
        )

        if _contains_too_much_hebrew(explanation):
            raise ValueError(
                "L'explication contient trop de texte hébreu "
                "non traduit."
            )

        if FORBIDDEN_COHEN_TRANSLATIONS.search(explanation):
            raise ValueError(
                "L'explication emploie prêtre ou sacrificateur "
                "au lieu de Cohen/Cohanim."
            )

        normalised_commentaries = (
            {}
            if exact_only
            else _normalise_commentaries(
                data.get("commentaries"),
                commentaries,
            )
        )

        return AlignedTranslationRun(
            translation_fr=translation,
            explanation_fr=explanation,
            commentaries=normalised_commentaries,
            confidence=_normalise_confidence(
                data.get("confidence")
            ),
            api=result,
        )
