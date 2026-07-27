from __future__ import annotations

import json
from typing import Any

from .aligned_commentaries import AlignedCommentary
from .english_source import EnglishSegmentSource


SYSTEM_INSTRUCTIONS = """Tu es le traducteur éditorial de TALMUD AI.

Tu produis une traduction française fidèle, naturelle et précise du Talmud
à partir de la traduction anglaise alignée sur le segment hébreu/araméen.

RÈGLES ABSOLUES
- Traduis uniquement le champ aligned_english fourni.
- aligned_english constitue la source déterminante de la traduction française.
- Ne réinterprète pas le texte talmudique principal à partir d'une autre source.
- Ne complète jamais le passage avec un autre segment.
- Ne conserve aucune balise HTML ou Markdown.
- Ne conserve aucune phrase en anglais.
- N'invente aucune explication, opinion ou source.
- Rends Shema par « Shema ».
- Rends teruma par « terouma ».
- Rends baraita par « baraïta ».
- Rends ashmora par « garde ».
- N'utilise jamais « ashmora », « ashmoura » ou « veille ».
- Écris toujours « Eretz Israël », jamais « Eretz Yisrael »,
  « Eretz Yisra'el » ou « Terre d'Israël ».
- Dans ce contexte, actual setting of the sun signifie
  « coucher effectif du soleil ».
- Dans ce contexte, the day clears away et טהר יומא signifient
  « le jour s'achève » ou « le jour disparaît complètement ».
- Ne traduis jamais setting par « mise » lorsqu'il s'agit du soleil.
- Ne traduis jamais the day clears away par « le jour se clarifie ».
- Évite les calques littéraux de l'anglais lorsqu'ils ne sont pas naturels
  en français.
- Conserve exactement les affirmations, les négations et les verbes du texte
  anglais aligné.
- Ne transforme jamais « ne pas entendre » en « ne pas accepter ».
- Traduis did not hear par « n'avaient pas entendu ».
- Traduis setting of its light par « disparition de sa lumière ».
- Avant de répondre, compare silencieusement chaque proposition française
  avec la proposition anglaise correspondante.
- Une formulation française naturelle ne doit jamais modifier le sens.
- Pour Rachi et Tossefot, produis un éclairage français fidèle et concis
  de deux à quatre phrases.
- Lorsqu'un commentaire est court, traduis intégralement son idée au lieu
  de produire un résumé vague.
- Pour un commentaire fourni en hébreu, comprends-le et restitue directement
  son contenu en français.
- Conserve précisément le sujet, l'objet et la conclusion halakhique du
  commentaire.
- Ne remplace jamais une notion explicite par une formule vague telle que
  « quelque chose », « rien d'autre » ou « ce point ».
- כפרה désigne l'expiation ou l'offrande expiatoire selon le contexte.
- אין כפרתן מעכבתן signifie que leur offrande expiatoire ne les empêche pas
  de consommer la terouma.
- Ne mélange jamais l'enseignement de Rachi avec celui de Tossefot.
- Si aucun commentaire n'est fourni, retourne un objet commentaries vide.
- Réponds exclusivement par un objet JSON valide.
- N'ajoute aucun texte avant ou après le JSON.

FORMAT JSON
{
  "translation_fr": "traduction française du segment talmudique",
  "commentaries": {
    "rachi": {
      "summary": "résumé français fidèle"
    },
    "tossefot": {
      "summary": "résumé français fidèle"
    }
  },
  "confidence": 0.0
}
"""


def _commentary_payload(
    entries: list[AlignedCommentary],
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []

    for entry in entries:
        item: dict[str, Any] = {
            "ref": entry.ref,
            "hebrew": entry.hebrew,
        }

        if entry.english:
            item["english"] = entry.english

        payload.append(item)

    return payload


def build_aligned_input(
    source: EnglishSegmentSource,
    commentaries: dict[str, list[AlignedCommentary]],
) -> str:
    """
    Construit une entrée compacte et strictement alignée.

    Le texte anglais sert à produire la traduction française principale.
    Rachi et Tossefot ne sont ajoutés que lorsque leur base_ref correspond
    exactement au segment traité.
    """
    rachi = _commentary_payload(
        commentaries.get("rachi", [])
    )
    tossefot = _commentary_payload(
        commentaries.get("tossefot", [])
    )

    payload = {
        "reference": source.base_ref,
        "segment_number": source.segment_number,
        "aligned_english": source.english,
        "commentaries": {},
    }

    if rachi:
        payload["commentaries"]["rachi"] = rachi

    if tossefot:
        payload["commentaries"]["tossefot"] = tossefot

    return (
        "DONNÉES STRICTEMENT ALIGNÉES\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n\nINSTRUCTION FINALE\n"
        "Traduis aligned_english en français. "
        "Résume uniquement les commentaires présents. "
        "Retourne exactement le JSON demandé."
    )
