from __future__ import annotations

import json
from typing import Any

from .aligned_commentaries import AlignedCommentary
from .english_source import EnglishSegmentSource


SYSTEM_INSTRUCTIONS = """Tu es le traducteur éditorial de TALMUD AI.

Tu dois distinguer strictement :
1. la traduction française exacte du segment hébreu/araméen ;
2. l'explication française apportée par l'édition anglaise alignée ;
3. les éclairages séparés de Rachi et de Tossefot.

RÈGLES ABSOLUES
- Le champ hebrew_aramaic est la source déterminante de translation_fr.
- Traduis dans translation_fr uniquement les mots et propositions réellement
  présents dans hebrew_aramaic.
- N'ajoute dans translation_fr aucune introduction, conclusion, référence,
  justification ou information absente de hebrew_aramaic.
- Le champ aligned_english sert uniquement à comprendre les ambiguïtés et à
  produire explanation_fr.
- Les développements explicatifs présents seulement dans aligned_english
  doivent aller dans explanation_fr, jamais dans translation_fr.
- explanation_fr doit expliquer le passage sans se présenter comme sa
  traduction et sans inventer d'information supplémentaire.
- Si aligned_english n'apporte aucune explication distincte,
  explanation_fr peut être une chaîne vide.
- Ne complète jamais le passage avec un autre segment.
- Ne conserve aucune balise HTML ou Markdown.
- Ne conserve aucune phrase en anglais.
- N'invente aucune explication, opinion ou source.
- Rends Shema par « Shema ».
- Rends teruma par « terouma ».
- Rends baraita par « baraïta ».
- Rends ashmora par « garde ».
- N'utilise jamais « ashmora », « ashmoura » ou « veille ».
- Rends כֹּהֵן par « Cohen ».
- Rends כֹּהֲנִים par « Cohanim ».
- Ne traduis jamais Cohen ou Cohanim par « prêtre », « prêtres »,
  « sacrificateur » ou « sacrificateurs ».
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
- Conserve exactement les affirmations, les négations et les verbes du
  segment hébreu/araméen dans translation_fr.
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
  "translation_fr": "traduction française exacte du segment hébreu/araméen",
  "explanation_fr": "explication française distincte ou chaîne vide",
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

    Le texte hébreu/araméen produit la traduction française principale.
    Le texte anglais sert uniquement à produire l'explication et à résoudre
    les ambiguïtés.
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
        "hebrew_aramaic": source.hebrew,
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
        "Traduis exactement hebrew_aramaic dans translation_fr. "
        "Place dans explanation_fr les développements utiles présents "
        "seulement dans aligned_english. "
        "Traduis Cohen par Cohen et Cohanim par Cohanim. "
        "Résume uniquement les commentaires présents. "
        "Retourne exactement le JSON demandé."
    )
