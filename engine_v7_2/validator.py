from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


GENERIC_SOURCE_NAMES = {
    "texte",
    "texte source",
    "passage",
    "passage source",
    "source",
    "talmud",
    "bavli",
    "guemara",
    "gemara",
    "segment central",
    "segment source",
    "hebreu",
    "araméen",
    "arameen",
}


COMMENTARY_ALIASES = {
    "rashi": "rachi",
    "rachi": "rachi",
    "tosafot": "tossefot",
    "tosafoth": "tossefot",
    "tossefot": "tossefot",
    "tossafot": "tossefot",
    "tossafoth": "tossefot",
    "ritva": "ritva",
    "rosh": "rosh",
    "roch": "rosh",
    "pnei yehoshoua": "pnei_yehoshoua",
    "pnei yehoshua": "pnei_yehoshoua",
}


HTML_FORMATTING_PATTERN = re.compile(
    r"</?\s*(?:b|strong)\s*>|"
    r"&lt;/?\s*(?:b|strong)\s*&gt;|"
    r"&amp;lt;/?\s*(?:b|strong)\s*&amp;gt;",
    flags=re.IGNORECASE,
)


HEBREW_LETTER_PATTERN = re.compile(
    r"[\u05d0-\u05ea]"
)


LATIN_LETTER_PATTERN = re.compile(
    r"[A-Za-zÀ-ÖØ-öø-ÿ]"
)


def normalize_source_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    normalized = unicodedata.normalize(
        "NFKD",
        text,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = normalized.replace("_", " ")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("’", "'")
    normalized = normalized.replace("`", "'")

    return " ".join(normalized.split())


def canonical_commentary_name(
    value: Any,
) -> str | None:
    normalized = normalize_source_name(value)

    if normalized in COMMENTARY_ALIASES:
        return COMMENTARY_ALIASES[normalized]

    for alias, canonical in COMMENTARY_ALIASES.items():
        if normalized.startswith(alias + " "):
            return canonical

    return None


def canonical_source_name(value: Any) -> str:
    normalized = normalize_source_name(value)

    if not normalized:
        return ""

    if normalized in GENERIC_SOURCE_NAMES:
        return "texte"

    commentary = canonical_commentary_name(
        normalized
    )

    if commentary:
        return commentary

    return normalized.replace(" ", "_")


def _canonical_available(
    available_commentaries: set[str],
) -> set[str]:
    return {
        canonical_source_name(name)
        for name in available_commentaries
        if canonical_source_name(name)
    }


def _contains_untranslated_hebrew(
    text: str,
) -> bool:
    """
    Autorise quelques termes hébreux isolés dans une phrase française,
    mais refuse un résumé resté majoritairement en hébreu.

    Un minimum de douze lettres hébraïques évite de refuser des termes
    indispensables comme Shema, terouma ou une courte citation.
    """
    hebrew_count = len(
        HEBREW_LETTER_PATTERN.findall(text)
    )
    latin_count = len(
        LATIN_LETTER_PATTERN.findall(text)
    )

    if hebrew_count < 12:
        return False

    total = hebrew_count + latin_count

    if total == 0:
        return False

    return hebrew_count / total >= 0.25


def _validate_translation(
    value: Any,
    *,
    field_name: str,
    errors: list[str],
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        errors.append(
            f"{field_name} est vide."
        )
        return ""

    text = value.strip()

    if HTML_FORMATTING_PATTERN.search(text):
        errors.append(
            f"{field_name} contient une balise "
            "b ou strong."
        )

    if (
        text.startswith("```")
        or text.endswith("```")
    ):
        errors.append(
            f"{field_name} contient un bloc Markdown."
        )

    return text


def _validate_sources(
    value: Any,
    *,
    available: set[str],
    errors: list[str],
) -> set[str]:
    if not isinstance(value, list):
        errors.append(
            "sources_used doit être une liste."
        )
        return set()

    canonical_sources: list[str] = []

    for index, source in enumerate(value):
        if not isinstance(source, str):
            errors.append(
                f"sources_used[{index}] doit être "
                "une chaîne."
            )
            continue

        canonical = canonical_source_name(source)

        if (
            canonical
            and canonical not in canonical_sources
        ):
            canonical_sources.append(canonical)

    if "texte" not in canonical_sources:
        errors.append(
            'sources_used doit contenir "texte".'
        )

    claimed = {
        source
        for source in canonical_sources
        if source != "texte"
    }

    invented = claimed - available

    if invented:
        errors.append(
            "Commentaires déclarés mais absents : "
            + ", ".join(sorted(invented))
        )

    return claimed


def _validate_commentaries(
    value: Any,
    *,
    available: set[str],
    claimed: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(
            "study.commentaries doit être un objet."
        )
        return

    seen: set[str] = set()

    for raw_name, entry in value.items():
        canonical = canonical_source_name(
            raw_name
        )

        if canonical in seen:
            errors.append(
                f"Le commentaire {canonical} "
                "apparaît plusieurs fois."
            )
            continue

        seen.add(canonical)

        if canonical not in available:
            errors.append(
                f"Le commentaire {canonical} "
                "est absent des sources."
            )

        if not isinstance(entry, dict):
            errors.append(
                f"study.commentaries.{raw_name} "
                "doit être un objet."
            )
            continue

        available_flag = entry.get(
            "available"
        )
        source_used = entry.get(
            "source_used"
        )
        summary = entry.get(
            "summary"
        )

        if available_flag is not True:
            errors.append(
                f"study.commentaries.{raw_name}."
                "available doit valoir true."
            )

        if not isinstance(source_used, bool):
            errors.append(
                f"study.commentaries.{raw_name}."
                "source_used doit être un booléen."
            )

        if not isinstance(summary, str):
            errors.append(
                f"study.commentaries.{raw_name}."
                "summary doit être une chaîne."
            )
            summary_text = ""
        else:
            summary_text = summary.strip()

        if HTML_FORMATTING_PATTERN.search(
            summary_text
        ):
            errors.append(
                f"Le commentaire {canonical} "
                "contient une balise HTML."
            )

        if _contains_untranslated_hebrew(
            summary_text
        ):
            errors.append(
                f"L'éclairage de {canonical} "
                "contient trop de texte hébreu non traduit."
            )

        if (
            source_used is True
            and not summary_text
        ):
            errors.append(
                f"Le commentaire {canonical} est utilisé "
                "mais son éclairage est vide."
            )

        if (
            summary_text
            and source_used is not True
        ):
            errors.append(
                f"Le commentaire {canonical} contient "
                "un éclairage mais source_used "
                "ne vaut pas true."
            )

        if (
            source_used is True
            and canonical not in claimed
        ):
            errors.append(
                f"Le commentaire {canonical} est utilisé "
                "mais absent de sources_used."
            )

        if (
            canonical in claimed
            and source_used is not True
        ):
            errors.append(
                f"Le commentaire {canonical} figure "
                "dans sources_used mais n'est pas "
                "marqué utilisé."
            )

        if len(summary_text) > 650:
            warnings.append(
                f"L'éclairage de {canonical} "
                "dépasse 650 caractères."
            )

    missing_claimed = claimed - seen

    if missing_claimed:
        errors.append(
            "Commentaires utilisés mais absents "
            "de study : "
            + ", ".join(sorted(missing_claimed))
        )


def _validate_study(
    value: Any,
    *,
    translation: str,
    available: set[str],
    claimed: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(
            "study doit être un objet."
        )
        return

    study_translation = _validate_translation(
        value.get("translation"),
        field_name="study.translation",
        errors=errors,
    )

    if (
        translation
        and study_translation
        and translation != study_translation
    ):
        errors.append(
            "study.translation ne correspond pas "
            "à translation_fr."
        )

    explanation = value.get(
        "explanation",
        "",
    )

    if not isinstance(explanation, str):
        errors.append(
            "study.explanation doit être une chaîne."
        )
    elif explanation.strip():
        warnings.append(
            "study.explanation n'est pas vide "
            "en mode léger."
        )

    _validate_commentaries(
        value.get("commentaries"),
        available=available,
        claimed=claimed,
        errors=errors,
        warnings=warnings,
    )

    confidence = value.get("confidence")

    if not isinstance(
        confidence,
        (int, float),
    ):
        errors.append(
            "study.confidence doit être un nombre."
        )
    elif not 0 <= float(confidence) <= 1:
        errors.append(
            "study.confidence doit être compris "
            "entre 0 et 1."
        )


def validate_editorial_result(
    payload: dict[str, Any],
    *,
    available_commentaries: set[str],
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        return ValidationResult(
            valid=False,
            errors=[
                "Le résultat éditorial doit être "
                "un objet."
            ],
            warnings=[],
        )

    translation = _validate_translation(
        payload.get("translation_fr"),
        field_name="translation_fr",
        errors=errors,
    )

    explanation = payload.get(
        "explanation_fr",
        "",
    )

    if not isinstance(explanation, str):
        errors.append(
            "explanation_fr doit être une chaîne."
        )
    elif explanation.strip():
        warnings.append(
            "explanation_fr n'est pas vide "
            "en mode léger."
        )

    confidence = payload.get("confidence")

    if not isinstance(
        confidence,
        (int, float),
    ):
        errors.append(
            "confidence doit être un nombre."
        )
    elif not 0 <= float(confidence) <= 1:
        errors.append(
            "confidence doit être compris "
            "entre 0 et 1."
        )
    elif float(confidence) < 0.70:
        warnings.append(
            "Confiance inférieure à 0,70 : "
            "vérification humaine recommandée."
        )

    available = _canonical_available(
        available_commentaries
    )

    claimed = _validate_sources(
        payload.get("sources_used"),
        available=available,
        errors=errors,
    )

    discouraged = {
        "ashmoura": "Employer « garde ».",
        "jour bon": "Employer « Yom Tov ».",
    }

    lowered_translation = translation.lower()

    for forbidden, instruction in (
        discouraged.items()
    ):
        if forbidden in lowered_translation:
            errors.append(
                f"Terme interdit « {forbidden} ». "
                f"{instruction}"
            )

    html = payload.get("html")

    if not isinstance(html, str):
        errors.append(
            "html doit être une chaîne."
        )
    elif re.search(
        r"&lt;/?\s*(?:b|strong)\s*&gt;|"
        r"&amp;lt;/?\s*(?:b|strong)\s*&amp;gt;",
        html,
        flags=re.IGNORECASE,
    ):
        errors.append(
            "Le HTML contient une balise "
            "de formatage visible."
        )

    _validate_study(
        payload.get("study"),
        translation=translation,
        available=available,
        claimed=claimed,
        errors=errors,
        warnings=warnings,
    )

    if payload.get("mode") != "light":
        warnings.append(
            "Le résultat n'est pas explicitement "
            "marqué mode light."
        )

    return ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )
