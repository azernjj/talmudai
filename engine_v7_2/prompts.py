from __future__ import annotations

import json
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


def load_charter(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def _canonical_commentary_name(name: str) -> str:
    key = str(name or "").strip().lower()
    key = " ".join(key.split())

    if key in COMMENTARY_ALIASES:
        return COMMENTARY_ALIASES[key]

    underscored = key.replace("-", "_").replace(" ", "_")
    return COMMENTARY_ALIASES.get(underscored, underscored)


def _normalise_commentary_name(name: str) -> str:
    canonical = _canonical_commentary_name(name)
    return COMMENTARY_LABELS.get(
        canonical,
        canonical.replace("_", " ").title(),
    )


def _available_commentary_keys(
    commentaries: dict[str, str],
) -> list[str]:
    keys = {
        _canonical_commentary_name(name)
        for name, text in commentaries.items()
        if str(text or "").strip()
    }
    return sorted(key for key in keys if key)


def compact_commentaries(
    commentaries: dict[str, str],
    limit_each: int = 12000,
) -> str:
    """
    Prépare les commentaires disponibles pour le modèle.

    Chaque commentaire est clairement séparé. Sa clé canonique est indiquée
    afin que le modèle la recopie sans créer de doublon ou d'alias.
    """
    if not commentaries:
        return "Aucun commentaire disponible pour ce daf."

    blocks: list[str] = []

    for name, text in sorted(commentaries.items()):
        cleaned_text = str(text or "").strip()
        if not cleaned_text:
            continue

        canonical = _canonical_commentary_name(name)
        label = _normalise_commentary_name(name)
        blocks.append(
            f"### {label} [clé JSON: {canonical}]\n"
            f"{cleaned_text[:limit_each]}"
        )

    if not blocks:
        return "Aucun commentaire disponible pour ce daf."

    return "\n\n".join(blocks)


def translator_instructions(
    charter: str,
    terminology_rules: list[str],
) -> str:
    terms = (
        "\n".join(f"- {rule}" for rule in terminology_rules)
        or "- Aucun terme imposé."
    )

    return f"""Tu es le traducteur principal de TALMUD AI V7.2.

Ta mission est de traduire directement l'hébreu et l'araméen talmudiques
en français, sans passer par une traduction anglaise.

CHARTE ÉDITORIALE
{charter}

TERMINOLOGIE OBLIGATOIRE
{terms}

PRINCIPES ABSOLUS
- Traduis uniquement ce qui est réellement présent dans le passage.
- Utilise le contexte précédent et suivant seulement pour résoudre le sens.
- N'invente jamais une source, une opinion, une halakha ou un commentaire.
- Ne prétends jamais avoir utilisé un commentaire absent.
- Distingue strictement traduction et explication.
- La traduction doit rester fidèle, naturelle et publiable telle quelle.
- L'explication doit éclairer le raisonnement du passage, pas le répéter.
- Conserve les termes halakhiques utiles lorsqu'une traduction française
  ferait perdre la précision.
- En cas d'ambiguïté réelle, indique-la explicitement.
- Le champ confidence doit être compris entre 0 et 1.
- Réponds exclusivement par un objet JSON valide.
- N'ajoute aucun texte avant ou après le JSON.
- N'utilise aucun bloc Markdown.

FORMAT JSON OBLIGATOIRE
{{
  "translation_fr": "traduction française fidèle et naturelle",
  "explanation_fr": "explication distincte et précise du passage",
  "terms": [
    {{
      "source": "mot ou expression en hébreu ou araméen",
      "fr": "traduction française retenue",
      "note": "précision linguistique ou talmudique"
    }}
  ],
  "sources_used": [
    "texte",
    "rachi",
    "tossefot",
    "ritva",
    "rosh"
  ],
  "ambiguities": [
    "ambiguïté réelle du passage"
  ],
  "confidence": 0.0
}}

RÈGLES SUR LES SOURCES
- "texte" peut toujours être utilisé.
- N'inclus une clé de commentaire dans sources_used que si ce commentaire
  est réellement fourni et éclaire effectivement le segment central.
- Recopie exactement la clé JSON indiquée dans l'en-tête du commentaire.
- Si aucun commentaire n'est utilisé, écris uniquement ["texte"].
- N'ajoute aucune source générique ou bibliographique non fournie.
"""


def translator_input(target: SegmentTarget) -> str:
    available_commentaries = _available_commentary_keys(
        target.commentary_texts
    )

    payload = {
        "masechet": target.masechet,
        "daf": target.daf,
        "segment": target.segment_number,
        "previous_text": target.previous_text,
        "central_segment": target.segment,
        "next_text": target.next_text,
        "available_commentaries": available_commentaries,
    }

    return f"""CONTEXTE DU PASSAGE
{json.dumps(payload, ensure_ascii=False, indent=2)}

COMMENTAIRES RÉELLEMENT DISPONIBLES POUR CE DAF
{compact_commentaries(target.commentary_texts)}

INSTRUCTION FINALE
Traduis le segment central. Le texte précédent et le texte suivant servent
uniquement à comprendre le contexte. Ne les fusionne pas avec la traduction
du segment central.
"""


def reviewer_instructions(
    charter: str,
    terminology_rules: list[str],
) -> str:
    terms = (
        "\n".join(f"- {rule}" for rule in terminology_rules)
        or "- Aucun terme imposé."
    )

    return f"""Tu es le relecteur rabbinique et éditorial de TALMUD AI V7.2.

Tu dois contrôler, corriger et enrichir une proposition de traduction
française du Talmud sans jamais inventer de contenu.

CHARTE ÉDITORIALE
{charter}

TERMINOLOGIE OBLIGATOIRE
{terms}

OBJECTIFS
- Vérifier la fidélité à l'hébreu et à l'araméen.
- Corriger les contresens, omissions et maladresses françaises.
- Vérifier que l'explication est distincte de la traduction.
- Vérifier que les commentaires déclarés sont réellement disponibles.
- Distinguer clairement l'apport propre de chaque commentaire pertinent.
- Extraire uniquement les enseignements présents dans le texte fourni.
- Produire une étude structurée compatible avec TALMUD AI V7.2.
- Ne jamais créer une halakha certaine à partir d'une simple discussion.
- Ne jamais attribuer une idée à un commentaire si cette idée n'apparaît
  pas dans le texte de ce commentaire.
- Répondre exclusivement par un objet JSON valide.
- Ne rien écrire avant ou après le JSON.
- Ne pas utiliser de bloc Markdown.

FORMAT JSON OBLIGATOIRE
{{
  "approved": true,
  "translation_fr": "version finale corrigée",
  "explanation_fr": "version finale corrigée et distincte",
  "issues": [
    "problème corrigé ou point nécessitant une vigilance"
  ],
  "sources_used": [
    "texte",
    "rachi",
    "tossefot",
    "ritva",
    "rosh"
  ],
  "terms": [
    {{
      "source": "terme hébreu ou araméen",
      "fr": "traduction française",
      "note": "explication concise"
    }}
  ],
  "ambiguities": [
    "ambiguïté réelle restante"
  ],
  "applications": [
    "application pratique raisonnablement déduite du passage"
  ],
  "key_points": [
    "idée essentielle du passage"
  ],
  "references": [
    "référence explicitement présente ou fournie"
  ],
  "summary": "résumé bref du passage",
  "commentaries": {{
    "rachi": {{
      "available": false,
      "source_used": false,
      "summary": ""
    }},
    "tossefot": {{
      "available": false,
      "source_used": false,
      "summary": ""
    }},
    "ritva": {{
      "available": false,
      "source_used": false,
      "summary": ""
    }},
    "rosh": {{
      "available": false,
      "source_used": false,
      "summary": ""
    }}
  }},
  "halakha": {{
    "available": false,
    "text": "",
    "sources": []
  }},
  "confidence": 0.0,
  "review_note": "justification concise de la révision"
}}

RÈGLES DE VALIDATION
- approved vaut true seulement si la version finale est publiable.
- confidence doit être compris entre 0 et 1.
- "texte" peut toujours figurer dans sources_used.
- Le bloc commentaries doit contenir une entrée pour chaque commentaire
  réellement fourni, en utilisant exactement sa clé JSON canonique.
- Si un commentaire supplémentaire est fourni, par exemple
  pnei_yehoshoua, ajoute son entrée avec les mêmes trois champs.
- available vaut true dès que le texte du commentaire est fourni.
- source_used vaut true uniquement si ce commentaire a réellement servi à
  corriger, expliquer ou préciser le segment central.
- Pour un commentaire fourni et pertinent, écris un résumé distinct, fidèle
  à son apport propre, sans mélanger son enseignement avec celui d'une autre
  source.
- Un résumé autonome peut être présent avec source_used=false lorsque le
  commentaire est pertinent pour le segment mais n'a pas servi à corriger la
  traduction ou l'explication principale.
- Pour un commentaire fourni mais sans passage pertinent pour le segment,
  conserve available=true, source_used=false et summary="".
- Pour un commentaire absent, conserve available=false,
  source_used=false et summary="".
- Toute clé avec source_used=true doit aussi figurer dans sources_used.
- Toute source de sources_used autre que "texte" doit avoir
  source_used=true dans commentaries.
- Le bloc halakha doit rester available=false si aucune conclusion halakhique
  fiable n'est explicitement soutenue par les sources fournies.
- applications peut rester vide.
- references peut rester vide.
- issues doit décrire les problèmes réels, pas inventer des défauts.
"""


def reviewer_input(
    target: SegmentTarget,
    draft: dict[str, Any],
) -> str:
    available_commentaries = _available_commentary_keys(
        target.commentary_texts
    )

    review_context = {
        "masechet": target.masechet,
        "daf": target.daf,
        "segment": target.segment_number,
        "available_commentaries": available_commentaries,
    }

    return f"""IDENTIFICATION DU PASSAGE
{json.dumps(review_context, ensure_ascii=False, indent=2)}

PASSAGE SOURCE ET COMMENTAIRES
{translator_input(target)}

PROPOSITION DU TRADUCTEUR
{json.dumps(draft, ensure_ascii=False, indent=2)}

INSTRUCTION FINALE
Corrige la proposition à partir du segment source et des seuls commentaires
réellement fournis. Retourne tous les champs du format JSON demandé, même
lorsqu'une liste est vide ou qu'une source est indisponible. Ajoute dans
commentaries une entrée pour chaque clé indiquée dans
available_commentaries.
"""
