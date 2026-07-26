from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import SegmentTarget


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


def load_charter(path: str | Path) -> str:
    return Path(path).read_text(
        encoding="utf-8"
    )


def _canonical_commentary_name(
    name: str,
) -> str:
    key = str(name or "").strip().lower()
    key = " ".join(key.split())

    if key in COMMENTARY_ALIASES:
        return COMMENTARY_ALIASES[key]

    underscored = (
        key
        .replace("-", "_")
        .replace(" ", "_")
    )

    return COMMENTARY_ALIASES.get(
        underscored,
        underscored,
    )


def _normalise_commentary_name(
    name: str,
) -> str:
    canonical = _canonical_commentary_name(
        name
    )

    return COMMENTARY_LABELS.get(
        canonical,
        canonical.replace("_", " ").title(),
    )


def _available_commentary_keys(
    commentaries: dict[str, str],
) -> list[str]:
    available = {
        _canonical_commentary_name(name)
        for name, text in commentaries.items()
        if str(text or "").strip()
    }

    ordered = [
        key
        for key in COMMENTARY_ORDER
        if key in available
    ]

    ordered.extend(
        sorted(
            available.difference(
                COMMENTARY_ORDER
            )
        )
    )

    return ordered


def _clean_plain_text(value: Any) -> str:
    text = str(value or "")

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
    text = re.sub(
        r"&amp;lt;/?\s*(?:b|strong)\s*&amp;gt;",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return " ".join(text.split())


def _clip(
    value: Any,
    limit: int,
) -> str:
    text = _clean_plain_text(value)

    if len(text) <= limit:
        return text

    clipped = text[:limit]

    if " " in clipped:
        clipped = clipped.rsplit(
            " ",
            1,
        )[0]

    return clipped.rstrip() + "…"


def _segment_source_text(
    segment: Any,
) -> str:
    if isinstance(segment, str):
        return _clean_plain_text(segment)

    if not isinstance(segment, dict):
        return _clean_plain_text(segment)

    for key in (
        "he",
        "hebrew",
        "text_he",
        "source_text",
        "source",
        "text",
    ):
        value = segment.get(key)

        if (
            isinstance(value, str)
            and value.strip()
        ):
            return _clean_plain_text(value)

    return ""


def compact_commentaries(
    commentaries: dict[str, str],
    limit_each: int = 500,
) -> str:
    """
    Envoie au modèle uniquement un court extrait de chaque méfarech.

    Cette limite constitue la principale protection du budget API.
    """
    if not commentaries:
        return "Aucun méfarech disponible."

    by_key: dict[str, str] = {}

    for name, text in commentaries.items():
        canonical = _canonical_commentary_name(
            name
        )
        cleaned = _clean_plain_text(text)

        if cleaned and canonical not in by_key:
            by_key[canonical] = cleaned

    blocks: list[str] = []

    for canonical in _available_commentary_keys(
        by_key
    ):
        text = by_key.get(
            canonical,
            "",
        )

        if not text:
            continue

        label = COMMENTARY_LABELS.get(
            canonical,
            canonical.replace(
                "_",
                " ",
            ).title(),
        )

        blocks.append(
            f"{label} [clé: {canonical}]\n"
            f"{_clip(text, limit_each)}"
        )

    if not blocks:
        return "Aucun méfarech disponible."

    return "\n\n".join(blocks)


def _compact_charter(charter: str) -> str:
    return _clip(
        charter,
        800,
    )


def _compact_terms(
    terminology_rules: list[str],
) -> str:
    rules = [
        _clip(rule, 120)
        for rule in terminology_rules[:8]
        if _clean_plain_text(rule)
    ]

    if not rules:
        return "- Aucune règle particulière."

    return "\n".join(
        f"- {rule}"
        for rule in rules
    )


def translator_instructions(
    charter: str,
    terminology_rules: list[str],
) -> str:
    return f"""Tu traduis directement le Talmud de l'hébreu et de l'araméen
en français pour TALMUD AI.

CHARTE ESSENTIELLE
{_compact_charter(charter)}

TERMINOLOGIE
{_compact_terms(terminology_rules)}

CONSIGNES
- Traduis uniquement central_text.
- Produis un français fidèle, naturel, précis et publiable.
- Ajoute une étude détaillée courte de deux à quatre phrases.
- Cette étude explique le raisonnement sans répéter la traduction.
- Rédige entièrement cette étude en français.
- Le contexte voisin sert uniquement à comprendre central_text.
- N'invente aucune source, halakha ou explication.
- Utilise uniquement les méfarchim réellement fournis.
- Pour chaque méfarech pertinent, écris en français un éclairage distinct
  d'une ou deux phrases courtes.
- Traduis en français l'idée du méfarech : ne recopie jamais un long passage
  hébreu ou araméen dans son éclairage.
- Omet tout méfarech absent ou non pertinent.
- N'ajoute ni HTML ni Markdown.
- Réponds uniquement par un objet JSON valide.

FORMAT JSON
{{
  "translation_fr": "traduction française",
  "explanation_fr": "étude détaillée courte en français",
  "commentaries": {{
    "rachi": "éclairage français concis",
    "tossefot": "éclairage français concis",
    "ritva": "éclairage français concis",
    "rosh": "éclairage français concis",
    "pnei_yehoshoua": "éclairage français concis"
  }},
  "sources_used": ["texte", "rachi"],
  "confidence": 0.0
}}

RÈGLES JSON
- Supprime de commentaries toute clé absente ou non pertinente.
- Utilise exactement les clés indiquées dans les extraits.
- sources_used commence toujours par "texte".
- Ajoute dans sources_used uniquement les commentaires réellement résumés.
- confidence doit être compris entre 0 et 1.
"""


def translator_input(
    target: SegmentTarget,
) -> str:
    payload = {
        "masechet": target.masechet,
        "daf": target.daf,
        "segment": target.segment_number,
        "previous_text": _clip(
            target.previous_text,
            180,
        ),
        "central_text": _segment_source_text(
            target.segment
        ),
        "next_text": _clip(
            target.next_text,
            180,
        ),
        "available_commentaries": (
            _available_commentary_keys(
                target.commentary_texts
            )
        ),
    }

    return f"""PASSAGE
{json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}

COURTS EXTRAITS DES MÉFARCHIM
{compact_commentaries(target.commentary_texts, limit_each=500)}

Traduis uniquement central_text et retourne uniquement le JSON demandé.
"""


def reviewer_instructions(
    charter: str,
    terminology_rules: list[str],
) -> str:
    """
    Prompt de secours appelé uniquement après un refus du validateur.
    """
    return f"""Tu corriges une courte traduction talmudique pour TALMUD AI.

CHARTE ESSENTIELLE
{_compact_charter(charter)}

TERMINOLOGIE
{_compact_terms(terminology_rules)}

- Corrige uniquement les erreurs réelles.
- N'invente rien.
- N'utilise que les méfarchim fournis.
- Rédige une étude détaillée courte de deux à quatre phrases.
- Cette étude explique le raisonnement sans répéter la traduction.
- Rédige entièrement cette étude en français.
- Rédige tous les éclairages entièrement en français.
- Ne recopie pas de long texte hébreu ou araméen.
- Chaque éclairage doit tenir en une ou deux phrases courtes.
- N'ajoute ni HTML ni Markdown.
- Réponds uniquement par un objet JSON valide.

FORMAT JSON
{{
  "translation_fr": "traduction française corrigée",
  "explanation_fr": "étude détaillée courte corrigée",
  "commentaries": {{
    "rachi": "éclairage français concis"
  }},
  "sources_used": ["texte", "rachi"],
  "confidence": 0.0
}}
"""


def reviewer_input(
    target: SegmentTarget,
    draft: dict[str, Any],
) -> str:
    context = {
        "masechet": target.masechet,
        "daf": target.daf,
        "segment": target.segment_number,
        "previous_text": _clip(
            target.previous_text,
            180,
        ),
        "central_text": _segment_source_text(
            target.segment
        ),
        "next_text": _clip(
            target.next_text,
            180,
        ),
        "available_commentaries": (
            _available_commentary_keys(
                target.commentary_texts
            )
        ),
        "draft": draft,
    }

    return f"""DONNÉES À CORRIGER
{json.dumps(context, ensure_ascii=False, separators=(",", ":"))}

COURTS EXTRAITS DES MÉFARCHIM
{compact_commentaries(target.commentary_texts, limit_each=500)}

Retourne uniquement le JSON final corrigé.
"""
