from __future__ import annotations

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
    "contexte",
    "contexte du passage",
    "contexte talmudique",
    "segment central",
    "segment source",
    "hebreu",
    "araméen",
    "arameen",
    "hebreu et arameen",
    "hébreu et araméen",
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

STANDARD_COMMENTARIES = {
    "rachi",
    "tossefot",
    "ritva",
    "rosh",
}


def normalize_source_name(value: Any) -> str:
    text = str(value or "").strip().lower()

    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = normalized.replace("_", " ")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("’", "'")
    normalized = normalized.replace("`", "'")
    normalized = " ".join(normalized.split())

    return normalized


def canonical_commentary_name(value: Any) -> str | None:
    normalized = normalize_source_name(value)

    if normalized in COMMENTARY_ALIASES:
        return COMMENTARY_ALIASES[normalized]

    for alias, canonical in COMMENTARY_ALIASES.items():
        if normalized.startswith(alias + " "):
            return canonical

    return None


def canonical_source_name(value: Any) -> str:
    """
    Retourne une clé canonique stable pour une source.
    """
    normalized = normalize_source_name(value)

    if not normalized:
        return ""

    if normalized in GENERIC_SOURCE_NAMES:
        return "texte"

    known = canonical_commentary_name(normalized)
    if known:
        return known

    return normalized.replace(" ", "_")


def _validate_string_list(
    value: Any,
    field_name: str,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field_name} doit être une liste.")
        return []

    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(
                f"{field_name}[{index}] doit être une chaîne."
            )
            continue

        text = item.strip()
        if text:
            result.append(text)

    return result


def _validate_study_block(
    study: Any,
    *,
    available_commentaries: set[str],
    claimed_commentaries: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(study, dict):
        errors.append("study doit être un objet.")
        return

    translation = study.get("translation")
    explanation = study.get("explanation")

    if not isinstance(translation, str):
        errors.append("study.translation doit être une chaîne.")
    elif not translation.strip():
        errors.append("study.translation est vide.")

    if not isinstance(explanation, str):
        errors.append("study.explanation doit être une chaîne.")
    elif not explanation.strip():
        errors.append("study.explanation est vide.")

    commentaries = study.get("commentaries")
    if not isinstance(commentaries, dict):
        errors.append("study.commentaries doit être un objet.")
    else:
        available = {
            canonical_source_name(name)
            for name in available_commentaries
            if canonical_source_name(name)
        }

        expected = STANDARD_COMMENTARIES | available
        seen_canonical: set[str] = set()
        entries_by_canonical: dict[str, dict[str, Any]] = {}

        for name, entry in commentaries.items():
            normalized_name = normalize_source_name(name)
            canonical = canonical_source_name(name)

            if normalized_name in {"rashi", "tosafot", "tosafoth"}:
                errors.append(
                    f"La clé historique {name} est interdite ; "
                    f"utiliser {canonical}."
                )

            if canonical in seen_canonical:
                errors.append(
                    f"Le commentaire {canonical} apparaît plusieurs fois "
                    "sous des alias différents."
                )
            else:
                seen_canonical.add(canonical)

            if not isinstance(entry, dict):
                errors.append(
                    f"study.commentaries.{name} doit être un objet."
                )
                continue

            entries_by_canonical[canonical] = entry

            available_flag = entry.get("available")
            source_used = entry.get("source_used")
            summary = entry.get("summary")

            if not isinstance(available_flag, bool):
                errors.append(
                    f"study.commentaries.{name}.available "
                    "doit être un booléen."
                )

            if not isinstance(source_used, bool):
                errors.append(
                    f"study.commentaries.{name}.source_used "
                    "doit être un booléen."
                )

            if not isinstance(summary, str):
                errors.append(
                    f"study.commentaries.{name}.summary "
                    "doit être une chaîne."
                )
                summary_text = ""
            else:
                summary_text = summary.strip()

            actually_available = canonical in available

            if canonical not in expected:
                errors.append(
                    f"Le commentaire {canonical} n'est ni standard "
                    "ni présent dans les sources fournies."
                )

            if available_flag is True and not actually_available:
                errors.append(
                    f"Le commentaire {canonical} est déclaré "
                    "disponible dans study mais absent des sources."
                )

            if actually_available and available_flag is not True:
                errors.append(
                    f"Le commentaire {canonical} est fourni "
                    "mais study.available ne vaut pas true."
                )

            if source_used is True and not actually_available:
                errors.append(
                    f"Le commentaire {canonical} est déclaré "
                    "utilisé mais absent des sources."
                )

            if source_used is True and available_flag is not True:
                errors.append(
                    f"Le commentaire {canonical} est utilisé "
                    "mais marqué indisponible."
                )

            if summary_text and not actually_available:
                errors.append(
                    f"Un résumé de {canonical} est présent "
                    "alors que la source est absente."
                )

            if source_used is True and not summary_text:
                errors.append(
                    f"Le commentaire {canonical} est utilisé "
                    "mais son résumé est vide."
                )

            claimed = canonical in claimed_commentaries

            if source_used is True and not claimed:
                errors.append(
                    f"Le commentaire {canonical} est marqué utilisé "
                    "dans study mais absent de sources_used."
                )

            if claimed and source_used is not True:
                errors.append(
                    f"Le commentaire {canonical} figure dans sources_used "
                    "mais study.source_used ne vaut pas true."
                )

        missing_entries = expected - set(entries_by_canonical)

        if missing_entries:
            errors.append(
                "Entrées de commentaires manquantes dans study : "
                + ", ".join(sorted(missing_entries))
            )

    halakha = study.get("halakha")
    if not isinstance(halakha, dict):
        errors.append("study.halakha doit être un objet.")
    else:
        available_flag = halakha.get("available")
        text = halakha.get("text")
        sources = halakha.get("sources")

        if not isinstance(available_flag, bool):
            errors.append(
                "study.halakha.available doit être un booléen."
            )

        if not isinstance(text, str):
            errors.append("study.halakha.text doit être une chaîne.")

        source_list = _validate_string_list(
            sources,
            "study.halakha.sources",
            errors,
        )

        if available_flag is True and not str(text or "").strip():
            errors.append(
                "study.halakha est marqué disponible mais son texte est vide."
            )

        if str(text or "").strip() and available_flag is not True:
            warnings.append(
                "Un texte halakhique est présent mais "
                "study.halakha.available vaut false."
            )

        if str(text or "").strip() and not source_list:
            warnings.append(
                "Le bloc halakhique contient un texte sans source déclarée."
            )

    _validate_string_list(
        study.get("applications"),
        "study.applications",
        errors,
    )
    _validate_string_list(
        study.get("key_points"),
        "study.key_points",
        errors,
    )
    _validate_string_list(
        study.get("references"),
        "study.references",
        errors,
    )
    _validate_string_list(
        study.get("issues"),
        "study.issues",
        errors,
    )

    glossary = study.get("glossary")
    if not isinstance(glossary, list):
        errors.append("study.glossary doit être une liste.")
    else:
        for index, entry in enumerate(glossary):
            if not isinstance(entry, dict):
                errors.append(
                    f"study.glossary[{index}] doit être un objet."
                )
                continue

            source = entry.get("source")
            french = entry.get("french")
            note = entry.get("note")

            if not isinstance(source, str) or not source.strip():
                errors.append(
                    f"study.glossary[{index}].source est vide."
                )

            if not isinstance(french, str) or not french.strip():
                errors.append(
                    f"study.glossary[{index}].french est vide."
                )

            if not isinstance(note, str):
                errors.append(
                    f"study.glossary[{index}].note doit être une chaîne."
                )

    summary = study.get("summary")
    review_note = study.get("review_note")

    if not isinstance(summary, str):
        errors.append("study.summary doit être une chaîne.")

    if not isinstance(review_note, str):
        errors.append("study.review_note doit être une chaîne.")

    confidence = study.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append("study.confidence doit être un nombre.")
    elif not 0 <= float(confidence) <= 1:
        errors.append(
            "study.confidence doit être compris entre 0 et 1."
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
            errors=["Le résultat éditorial doit être un objet."],
            warnings=[],
        )

    translation = payload.get("translation_fr")
    explanation = payload.get("explanation_fr")

    if not isinstance(translation, str) or not translation.strip():
        errors.append("translation_fr est vide.")

    if not isinstance(explanation, str) or not explanation.strip():
        errors.append("explanation_fr est vide.")

    if isinstance(translation, str) and isinstance(explanation, str):
        if (
            translation.strip()
            and translation.strip() == explanation.strip()
        ):
            errors.append(
                "L'explication répète exactement la traduction."
            )

    confidence = payload.get("confidence")

    if not isinstance(confidence, (int, float)):
        errors.append("confidence doit être un nombre.")
    elif not 0 <= float(confidence) <= 1:
        errors.append(
            "confidence doit être compris entre 0 et 1."
        )
    elif float(confidence) < 0.70:
        warnings.append(
            "Confiance inférieure à 0,70 : "
            "vérification humaine recommandée."
        )

    available = {
        canonical_source_name(name)
        for name in available_commentaries
        if canonical_source_name(name)
    }

    sources = payload.get("sources_used", [])
    claimed_commentaries: set[str] = set()

    if not isinstance(sources, list):
        errors.append("sources_used doit être une liste.")
    else:
        for source in sources:
            canonical = canonical_source_name(source)

            if not canonical:
                continue

            if canonical == "texte":
                continue

            claimed_commentaries.add(canonical)

        invented_commentaries = claimed_commentaries - available

        if invented_commentaries:
            errors.append(
                "Commentaires déclarés mais absents : "
                + ", ".join(sorted(invented_commentaries))
            )

    discouraged = {
        "ashmoura": "Employer « garde ».",
        "jour bon": "Employer « Yom Tov ».",
    }

    combined = f"{translation or ''} {explanation or ''}".lower()

    for forbidden, instruction in discouraged.items():
        if forbidden in combined:
            errors.append(
                f"Terme interdit « {forbidden} ». {instruction}"
            )

    html = payload.get("html")
    if html is not None and not isinstance(html, str):
        errors.append("html doit être une chaîne.")

    study = payload.get("study")
    if study is not None:
        _validate_study_block(
            study,
            available_commentaries=available_commentaries,
            claimed_commentaries=claimed_commentaries,
            errors=errors,
            warnings=warnings,
        )

        if isinstance(study, dict):
            study_translation = study.get("translation")
            study_explanation = study.get("explanation")

            if (
                isinstance(translation, str)
                and isinstance(study_translation, str)
                and translation.strip() != study_translation.strip()
            ):
                errors.append(
                    "study.translation ne correspond pas à translation_fr."
                )

            if (
                isinstance(explanation, str)
                and isinstance(study_explanation, str)
                and explanation.strip() != study_explanation.strip()
            ):
                errors.append(
                    "study.explanation ne correspond pas à explanation_fr."
                )

    return ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )
