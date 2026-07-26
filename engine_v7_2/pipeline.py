from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .html_renderer import clean_model_markdown, render_study_html
from .models import CommentaryStudy, SegmentTarget, StudyBlock
from .reviewer import Reviewer
from .translator import Translator
from .validator import ValidationResult, validate_editorial_result


ENGINE_VERSION = "7.2"
SCHEMA_VERSION = "study-light-v7.2"


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
    "pnei_yehoshoua": "pnei_yehoshoua",
    "pnei-yehoshoua": "pnei_yehoshoua",
    "pnei yehoshoua": "pnei_yehoshoua",
    "pnei_yehoshua": "pnei_yehoshoua",
    "pnei yehoshua": "pnei_yehoshoua",
}


COMMENTARY_ORDER = (
    "rachi",
    "tossefot",
    "ritva",
    "rosh",
    "pnei_yehoshoua",
)


@dataclass
class PipelineResult:
    final: dict[str, Any]
    validation: ValidationResult
    metadata: dict[str, Any]


def _clean_text(value: Any) -> str:
    """
    Nettoie les marqueurs de mise en forme qui ne doivent pas apparaître
    dans la traduction publiée.
    """
    text = str(value or "").strip()

    text = re.sub(
        r"</?\s*(?:b|strong)\s*>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"&lt;/?\s*(?:b|strong)\s*&gt;",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return clean_model_markdown(text).strip()


def _normalise_source_name(value: Any) -> str:
    text = _clean_text(value).lower()
    text = text.replace("’", "'").replace("`", "'")
    text = " ".join(text.split())

    underscored = (
        text
        .replace("-", "_")
        .replace(" ", "_")
    )

    generic_aliases = {
        "guemara": "texte",
        "gemara": "texte",
        "talmud": "texte",
        "bavli": "texte",
        "texte_source": "texte",
        "passage": "texte",
        "passage_source": "texte",
    }

    if underscored in generic_aliases:
        return generic_aliases[underscored]

    return COMMENTARY_ALIASES.get(
        underscored,
        underscored,
    )


def _available_commentaries(
    target: SegmentTarget,
) -> set[str]:
    return {
        _normalise_source_name(name)
        for name, text in target.commentary_texts.items()
        if _clean_text(text)
    }


def _normalise_commentary_payload(
    target: SegmentTarget,
    data: dict[str, Any],
) -> tuple[dict[str, CommentaryStudy], list[str]]:
    """
    Conserve uniquement les commentaires réellement disponibles.

    Un commentaire fourni mais non pertinent reste disponible avec un
    résumé vide. Aucun texte ou commentaire absent n’est inventé.
    """
    available = _available_commentaries(target)

    payload = data.get("commentaries")
    if not isinstance(payload, dict):
        payload = {}

    summaries: dict[str, str] = {}

    for raw_name, raw_entry in payload.items():
        name = _normalise_source_name(raw_name)

        if name not in available:
            continue

        if isinstance(raw_entry, str):
            summary = _clean_text(raw_entry)

        elif isinstance(raw_entry, dict):
            summary = _clean_text(
                raw_entry.get("summary")
                or raw_entry.get("resume")
                or raw_entry.get("text")
            )

        else:
            summary = ""

        if summary:
            summaries[name] = summary

    ordered_names = [
        name
        for name in COMMENTARY_ORDER
        if name in available
    ]

    ordered_names.extend(
        sorted(
            available.difference(COMMENTARY_ORDER)
        )
    )

    studies: dict[str, CommentaryStudy] = {}

    for name in ordered_names:
        summary = summaries.get(name, "")

        studies[name] = CommentaryStudy(
            available=True,
            source_used=bool(summary),
            summary=summary,
        )

    sources_used = ["texte"]

    sources_used.extend(
        name
        for name in ordered_names
        if summaries.get(name)
    )

    return studies, sources_used


def _normalise_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, confidence))


def _build_study(
    target: SegmentTarget,
    data: dict[str, Any],
) -> tuple[StudyBlock, list[str]]:
    commentaries, sources_used = (
        _normalise_commentary_payload(
            target,
            data,
        )
    )

    study = StudyBlock(
        translation=_clean_text(
            data.get("translation_fr")
            or data.get("translation")
        ),
        explanation="",
        commentaries=commentaries,
        confidence=_normalise_confidence(
            data.get("confidence")
        ),
    )

    return study, sources_used


def _build_final(
    target: SegmentTarget,
    data: dict[str, Any],
) -> dict[str, Any]:
    study, sources_used = _build_study(
        target,
        data,
    )

    html = render_study_html(study)

    return {
        "translation_fr": study.translation,
        "explanation_fr": "",
        "sources_used": sources_used,
        "confidence": study.confidence,
        "review_note": "",
        "issues": [],
        "html": html,
        "study": study.to_dict(),
        "mode": "light",
    }


def _token_payload(
    api_result: Any | None,
) -> dict[str, int]:
    if api_result is None:
        return {
            "input": 0,
            "output": 0,
            "total": 0,
        }

    input_tokens = int(
        getattr(
            api_result,
            "input_tokens",
            0,
        )
        or 0
    )

    output_tokens = int(
        getattr(
            api_result,
            "output_tokens",
            0,
        )
        or 0
    )

    total_tokens = int(
        getattr(
            api_result,
            "total_tokens",
            input_tokens + output_tokens,
        )
        or input_tokens + output_tokens
    )

    return {
        "input": input_tokens,
        "output": output_tokens,
        "total": total_tokens,
    }


class EditorialPipeline:
    """
    Pipeline léger TALMUD AI V7.2.

    Fonctionnement normal :
    - un seul appel au traducteur ;
    - traduction française ;
    - éclairage concis des méfarchim pertinents ;
    - validation locale.

    Le relecteur devient un secours exceptionnel. Il est appelé uniquement
    si la première réponse possède une traduction mais échoue à la
    validation.
    """

    def __init__(
        self,
        translator: Translator,
        reviewer: Reviewer | None = None,
    ) -> None:
        self.translator = translator
        self.reviewer = reviewer

    def run(
        self,
        target: SegmentTarget,
    ) -> PipelineResult:
        translation_run = self.translator.translate(
            target
        )

        data = translation_run.draft

        if not isinstance(data, dict):
            raise TypeError(
                "Le traducteur doit renvoyer un objet JSON."
            )

        final = _build_final(
            target,
            data,
        )

        validation = validate_editorial_result(
            final,
            available_commentaries=(
                _available_commentaries(target)
            ),
        )

        reviewer_api = None
        reviewer_used = False

        if (
            not validation.valid
            and self.reviewer is not None
            and bool(final.get("translation_fr"))
        ):
            review_run = (
                self.reviewer.review_translation(
                    target,
                    data,
                )
            )

            reviewer_api = review_run.api
            reviewer_used = True

            final = _build_final(
                target,
                review_run.review,
            )

            validation = validate_editorial_result(
                final,
                available_commentaries=(
                    _available_commentaries(target)
                ),
            )

        translator_tokens = _token_payload(
            translation_run.api
        )

        reviewer_tokens = _token_payload(
            reviewer_api
        )

        metadata = {
            "engine_version": ENGINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "mode": "light",
            "generated_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "masechet": target.masechet,
            "daf": target.daf,
            "segment_number": target.segment_number,
            "segment_index": target.segment_index,
            "translator_model": getattr(
                self.translator,
                "model",
                None,
            ),
            "reviewer_model": (
                getattr(
                    self.reviewer,
                    "model",
                    None,
                )
                if reviewer_used
                else None
            ),
            "translator_response_id": getattr(
                translation_run.api,
                "response_id",
                None,
            ),
            "reviewer_response_id": getattr(
                reviewer_api,
                "response_id",
                None,
            ),
            "reviewer_used": reviewer_used,
            "tokens": {
                "translator": translator_tokens,
                "reviewer": reviewer_tokens,
                "total": (
                    translator_tokens["total"]
                    + reviewer_tokens["total"]
                ),
            },
            "commentaries_available": sorted(
                _available_commentaries(target)
            ),
            "commentaries_used": [
                source
                for source in final.get(
                    "sources_used",
                    [],
                )
                if source != "texte"
            ],
            "validation": {
                "valid": validation.valid,
                "errors": list(
                    validation.errors
                ),
                "warnings": list(
                    validation.warnings
                ),
            },
        }

        return PipelineResult(
            final=final,
            validation=validation,
            metadata=metadata,
        )
