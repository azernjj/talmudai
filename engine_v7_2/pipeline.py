from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .html_renderer import clean_model_markdown, render_study_html
from .models import (
    CommentaryStudy,
    GlossaryEntry,
    HalakhaStudy,
    SegmentTarget,
    StudyBlock,
)
from .reviewer import Reviewer
from .translator import Translator
from .validator import ValidationResult, validate_editorial_result


ENGINE_VERSION = "7.2"


@dataclass
class PipelineResult:
    """
    Résultat complet d'un passage traité par le moteur éditorial.

    - final : contenu destiné au corpus JSON ;
    - validation : résultat de la validation éditoriale ;
    - metadata : informations techniques, modèles et consommation de jetons.
    """

    final: dict[str, Any]
    validation: ValidationResult
    metadata: dict[str, Any]


def _clean_text(value: Any) -> str:
    """Convertit une valeur en texte propre sans lever d'exception."""
    if value is None:
        return ""
    return str(value).strip()


def _clean_string_list(value: Any) -> list[str]:
    """
    Normalise une valeur en liste de chaînes non vides, sans doublons,
    tout en conservant l'ordre d'origine.
    """
    if value is None:
        return []

    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        candidates = [value]

    result: list[str] = []
    seen: set[str] = set()

    for item in candidates:
        text = _clean_text(item)
        if not text:
            continue

        key = text.casefold()
        if key in seen:
            continue

        seen.add(key)
        result.append(text)

    return result


def _clean_confidence(value: Any) -> float:
    """Retourne un niveau de confiance compris entre 0 et 1."""
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, confidence))


def _normalise_source_name(value: Any) -> str:
    """
    Normalise un nom de source pour permettre les comparaisons entre
    les réponses du modèle et les noms des commentaires chargés.
    """
    text = _clean_text(value).lower()
    text = text.replace("’", "'").replace("`", "'")
    text = " ".join(text.split())

    aliases = {
        "guemara": "texte",
        "gemara": "texte",
        "talmud": "texte",
        "bavli": "texte",
        "texte source": "texte",
        "passage": "texte",
        "passage source": "texte",
        "rashi": "rachi",
        "rachi": "rachi",
        "tosafot": "tossefot",
        "tosafoth": "tossefot",
        "tossefot": "tossefot",
        "tossafot": "tossefot",
        "tossafoth": "tossefot",
        "roch": "rosh",
    }
    return aliases.get(text, text)


def _normalise_source_list(value: Any) -> list[str]:
    """
    Normalise et déduplique une liste de sources en conservant l'ordre.
    """
    result: list[str] = []
    seen: set[str] = set()

    for raw_source in _clean_string_list(value):
        source = _normalise_source_name(raw_source)
        if not source or source in seen:
            continue

        seen.add(source)
        result.append(source)

    return result


def _available_commentary_map(
    target: SegmentTarget,
) -> dict[str, str]:
    """
    Construit une table normalisée :
        nom normalisé -> nom réel présent dans commentary_texts.
    """
    result: dict[str, str] = {}

    for raw_name in target.commentary_texts:
        normalised = _normalise_source_name(raw_name)
        if normalised:
            result[normalised] = raw_name

    return result


def _build_commentary_studies(
    *,
    target: SegmentTarget,
    review: dict[str, Any],
    sources_used: list[str],
) -> dict[str, CommentaryStudy]:
    """
    Prépare les emplacements des commentaires pour le schéma V7.2.

    Le pipeline V7.2 Livrable 2A ne génère pas encore les résumés détaillés
    de chaque commentaire. Il indique uniquement leur disponibilité et
    s'ils ont réellement été déclarés comme utilisés par le modèle.
    """
    available = _available_commentary_map(target)
    used = {_normalise_source_name(source) for source in sources_used}

    commentary_payload = review.get("commentaries")
    if not isinstance(commentary_payload, dict):
        commentary_payload = {}

    normalised_payload: dict[str, Any] = {}

    for raw_name, raw_entry in commentary_payload.items():
        name = _normalise_source_name(raw_name)
        if name:
            normalised_payload[name] = raw_entry

    standard_names = ("rachi", "tossefot", "ritva", "rosh")
    all_names = list(standard_names)

    for name in available:
        if name not in all_names:
            all_names.append(name)

    result: dict[str, CommentaryStudy] = {}

    for name in all_names:
        raw_entry = normalised_payload.get(name, {})
        summary = ""

        if isinstance(raw_entry, str):
            summary = raw_entry.strip()
        elif isinstance(raw_entry, dict):
            summary = _clean_text(
                raw_entry.get("summary")
                or raw_entry.get("resume")
                or raw_entry.get("text")
            )

        is_available = name in available
        source_used = name in used and is_available

        # Sécurité : aucun résumé n'est conservé pour une source absente.
        if not is_available:
            summary = ""
            source_used = False

        result[name] = CommentaryStudy(
            available=is_available,
            summary=summary,
            source_used=source_used,
        )

    return result


def _build_glossary(review: dict[str, Any]) -> list[GlossaryEntry]:
    """
    Convertit le champ `terms` du traducteur ou du relecteur vers le
    glossaire structuré V7.2.
    """
    raw_terms = review.get("terms", [])
    if not isinstance(raw_terms, list):
        return []

    glossary: list[GlossaryEntry] = []

    for item in raw_terms:
        if not isinstance(item, dict):
            continue

        source = _clean_text(
            item.get("source")
            or item.get("term")
            or item.get("he")
            or item.get("aramaic")
        )
        french = _clean_text(
            item.get("fr")
            or item.get("french")
            or item.get("translation")
        )
        note = _clean_text(item.get("note"))

        if not source or not french:
            continue

        glossary.append(
            GlossaryEntry(
                source=source,
                french=french,
                note=note,
            )
        )

    return glossary


def _build_halakha(review: dict[str, Any]) -> HalakhaStudy:
    """
    Prépare le bloc halakhique s'il est déjà fourni par un futur module.

    Dans le Livrable 2A, ce bloc reste normalement vide. Cette fonction
    permet toutefois au pipeline de rester compatible avec les prochains
    livrables sans casser le format du corpus.
    """
    raw = review.get("halakha")

    if isinstance(raw, str):
        text = raw.strip()
        return HalakhaStudy(
            available=bool(text),
            text=text,
            sources=[],
        )

    if not isinstance(raw, dict):
        return HalakhaStudy()

    text = _clean_text(
        raw.get("text")
        or raw.get("summary")
        or raw.get("resume")
        or raw.get("halakha_fr")
    )
    sources = _clean_string_list(raw.get("sources"))

    return HalakhaStudy(
        available=bool(text),
        text=text,
        sources=sources,
    )


def _build_study_block(
    *,
    target: SegmentTarget,
    review: dict[str, Any],
) -> StudyBlock:
    """
    Transforme la réponse finale du relecteur en objet d'étude V7.2.
    """
    translation = clean_model_markdown(
        _clean_text(review.get("translation_fr"))
    )
    explanation = clean_model_markdown(
        _clean_text(review.get("explanation_fr"))
    )
    sources_used = _normalise_source_list(review.get("sources_used"))
    issues = _clean_string_list(review.get("issues"))
    ambiguities = _clean_string_list(review.get("ambiguities"))

    for ambiguity in ambiguities:
        if ambiguity not in issues:
            issues.append(ambiguity)

    applications = _clean_string_list(
        review.get("applications")
        or review.get("practical_applications")
    )
    key_points = _clean_string_list(
        review.get("key_points")
        or review.get("points_cles")
    )
    references = _clean_string_list(
        review.get("references")
        or review.get("cross_references")
    )

    return StudyBlock(
        translation=translation,
        explanation=explanation,
        commentaries=_build_commentary_studies(
            target=target,
            review=review,
            sources_used=sources_used,
        ),
        halakha=_build_halakha(review),
        applications=applications,
        glossary=_build_glossary(review),
        summary=_clean_text(review.get("summary")),
        key_points=key_points,
        references=references,
        confidence=_clean_confidence(review.get("confidence")),
        issues=issues,
        review_note=_clean_text(review.get("review_note")),
    )


def _render_html(study: StudyBlock) -> str:
    """
    Utilise le renderer V7.2 lorsqu'il accepte un bloc complet.

    Tant que l'ancien html_renderer.py est encore en place, la fonction
    retombe automatiquement sur la signature historique :
        render_study_html(translation, explanation)
    """
    try:
        return render_study_html(study)
    except (TypeError, AttributeError):
        return render_study_html(
            study.translation,
            study.explanation,
        )


def _token_payload(api_result: Any) -> dict[str, int]:
    """Extrait de manière sûre la consommation de jetons d'un appel API."""
    input_tokens = int(getattr(api_result, "input_tokens", 0) or 0)
    output_tokens = int(getattr(api_result, "output_tokens", 0) or 0)
    total_tokens = int(
        getattr(api_result, "total_tokens", input_tokens + output_tokens)
        or input_tokens + output_tokens
    )

    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": total_tokens,
    }


class EditorialPipeline:
    """
    Pipeline éditorial TALMUD AI V7.2.

    Étapes :
    1. traduction directe hébreu/araméen -> français ;
    2. relecture éditoriale et rabbinique ;
    3. construction du bloc d'étude structuré ;
    4. génération HTML ;
    5. validation ;
    6. production des métadonnées techniques.
    """

    def __init__(
        self,
        translator: Translator,
        reviewer: Reviewer,
    ) -> None:
        self.translator = translator
        self.reviewer = reviewer

    def run(self, target: SegmentTarget) -> PipelineResult:
        translation_run = self.translator.translate(target)

        review_run = self.reviewer.review_translation(
            target,
            translation_run.draft,
        )
        review = review_run.review

        if not isinstance(review, dict):
            raise TypeError(
                "Le relecteur doit renvoyer un objet JSON représenté "
                "par un dictionnaire Python."
            )

        study = _build_study_block(
            target=target,
            review=review,
        )
        html = _render_html(study)

        sources_used = _normalise_source_list(review.get("sources_used"))

        # Le format conserve les champs V7.1 afin que corpus_writer.py,
        # validator.py et le site actuel restent compatibles pendant
        # la migration vers V7.2.
        final: dict[str, Any] = {
            "translation_fr": study.translation,
            "explanation_fr": study.explanation,
            "sources_used": sources_used,
            "confidence": study.confidence,
            "review_note": study.review_note,
            "issues": study.issues,
            "html": html,
            "study": study.to_dict(),
        }

        validation = validate_editorial_result(
            final,
            available_commentaries=set(target.commentary_texts),
        )

        translator_tokens = _token_payload(translation_run.api)
        reviewer_tokens = _token_payload(review_run.api)

        metadata = {
            "engine_version": ENGINE_VERSION,
            "schema_version": "study-v7.2",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "masechet": target.masechet,
            "daf": target.daf,
            "segment_number": target.segment_number,
            "segment_index": target.segment_index,
            "translator_model": getattr(self.translator, "model", None),
            "reviewer_model": getattr(self.reviewer, "model", None),
            "translator_response_id": getattr(
                translation_run.api,
                "response_id",
                None,
            ),
            "reviewer_response_id": getattr(
                review_run.api,
                "response_id",
                None,
            ),
            "tokens": {
                "translator": translator_tokens,
                "reviewer": reviewer_tokens,
                "total": (
                    translator_tokens["total"]
                    + reviewer_tokens["total"]
                ),
            },
            "commentaries_available": sorted(target.commentary_texts),
            "commentaries_used": sorted(
                {
                    _normalise_source_name(source)
                    for source in sources_used
                    if _normalise_source_name(source) != "texte"
                }
            ),
            "validation": {
                "valid": validation.valid,
                "errors": list(validation.errors),
                "warnings": list(validation.warnings),
            },
        }

        return PipelineResult(
            final=final,
            validation=validation,
            metadata=metadata,
        )
