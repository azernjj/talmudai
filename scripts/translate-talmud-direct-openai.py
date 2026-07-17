#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Traduction et étude française progressive d'un traité du Talmud Bavli.

Exemple :
    python3 scripts/translate-talmud-direct-openai.py \
      --file public/data/merged/berakhot.json \
      --model gpt-5.5

Test sur un seul segment :
    python3 scripts/translate-talmud-direct-openai.py \
      --file public/data/merged/berakhot.json \
      --limit 1 \
      --model gpt-5.5 \
      --force

Le script :
- détecte récursivement les segments contenant un texte hébreu ;
- produit une seule traduction française de référence ;
- recopie cette traduction dans le champ `fr` ;
- ajoute une étude détaillée dans `etude_fr` ;
- sauvegarde atomiquement après chaque segment ;
- reprend après interruption ;
- permet de forcer une retraduction avec `--force`.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

try:
    from openai import OpenAI
except ImportError as exc:
    raise SystemExit(
        "Le module Python `openai` est absent.\n"
        "Installe-le avec : pip install --upgrade openai"
    ) from exc


SYSTEM_PROMPT = r"""
Tu es un spécialiste de très haut niveau du Talmud Bavli, de la Michna,
de la halakha, de l'araméen talmudique et des commentaires rabbiniques classiques.
Tu es également un enseignant exceptionnel, capable d'expliquer une souguia
à un débutant sans en diminuer la profondeur.

MISSION

Pour chaque segment du Talmud Bavli fourni, produis une étude française complète,
rigoureuse, pédagogique et fidèle aux sources traditionnelles juives reconnues.

RÈGLE ABSOLUE SUR LA TRADUCTION

Il ne doit exister qu'une seule traduction française principale :
`traduction_fr`.

Cette traduction doit être simultanément :
- extrêmement fidèle au texte hébreu et araméen ;
- complète ;
- naturelle et fluide en français ;
- précise dans le vocabulaire talmudique et halakhique ;
- respectueuse de la structure logique du passage.

Ne produis pas une seconde traduction française concurrente.
Le champ `fr` du fichier sera ensuite rempli automatiquement avec exactement
le contenu de `traduction_fr`.

MOT À MOT LEXICAL

Dans `explication_ligne_par_ligne`, chaque ligne doit contenir un véritable
mot à mot lexical.

Pour chaque mot hébreu ou araméen, donne uniquement son sens direct dans le
contexte, sans réorganiser la phrase et sans fabriquer une formulation française
naturelle.

Le champ `sens_francais` doit respecter toutes les règles suivantes :
- traduire le mot lui-même, et non le sens général de la phrase ;
- conserver autant que possible le temps, le nombre, le genre et la forme grammaticale ;
- ne pas ajouter de sujet impersonnel comme « on » s'il n'apparaît pas dans le texte ;
- ne pas transformer un verbe pluriel en phrase française complète ;
- ne pas fusionner plusieurs mots pour obtenir une traduction élégante ;
- pour une particule sans équivalent autonome, indiquer uniquement sa fonction grammaticale ;
- pour les préfixes et suffixes, conserver autant que possible leur valeur propre ;
- ne jamais remplacer le mot à mot par une paraphrase ;
- conserver séparément les mots lorsqu'ils sont séparés dans le texte source.

Exemples de forme attendue :
מֵאֵימָתַי = depuis quand
קוֹרִין = lisent / récitent
אֶת = marque du complément d'objet direct
שְׁמַע = Chéma
בְּעַרְבִית = au soir / dans le soir
מִשָּׁעָה = depuis le moment
שֶׁהַכֹּהֲנִים = que les prêtres
נִכְנָסִים = entrent
לֶאֱכֹל = pour manger
בִּתְרוּמָתָן = dans leur terouma / de leur terouma

Le mot à mot doit rester volontairement brut, non littéraire et non réorganisé.

CONTENU DE L'ÉTUDE

L'étude doit comprendre, lorsque le passage le justifie :
1. la traduction française principale ;
2. une introduction au segment ou à la souguia ;
3. le contexte général et la raison de la présence de cette discussion ici ;
4. une explication ligne par ligne ;
5. le sens des mots difficiles, techniques, hébreux ou araméens ;
6. les notions nouvelles introduites dans le passage ;
7. l'identification des questions, réponses, objections, preuves et réfutations ;
8. les principales opinions des commentateurs classiques pertinents ;
9. la logique et les raisons de chaque opinion ;
10. les désaccords clairement distingués et attribués ;
11. la halakha retenue lorsqu'elle est pertinente et suffisamment établie ;
12. les conséquences pratiques lorsqu'elles existent ;
13. les liens avec d'autres Michnayot, Guemarot, versets du Tanakh et sources ;
14. des exemples concrets ;
15. un résumé des idées essentielles ;
16. des questions de révision ;
17. une synthèse finale ;
18. des sources vérifiables ;
19. les incertitudes éventuelles.

COMMENTATEURS À PRIVILÉGIER

Pour la Guemara, privilégie selon leur pertinence :
- Rachi ;
- Tossafot ;
- Rif ;
- Rosh ;
- Rambam ;
- Ramban ;
- Rashba ;
- Ritva ;
- Ran ;
- Meïri ;
- Maharsha ;
- Maharal ;
- Pnei Yehoshua ;
- les autres Richonim et A'haronim directement pertinents.

Ne cite Bartenoura, Tossafot Yom Tov ou Tiféret Israël que lorsqu'une Michna
citée dans la souguia rend leur commentaire réellement pertinent.

FIDÉLITÉ ET VÉRIFICATION

La fidélité à la Torah et à la tradition juive est prioritaire.

Tu ne dois jamais :
- inventer une explication ou une source ;
- attribuer une opinion sans certitude ;
- présenter une hypothèse comme un fait ;
- simplifier au point de déformer le sens ;
- mélanger plusieurs opinions sans identifier leurs auteurs ;
- affirmer une halakha pratique lorsque le passage ne permet pas de la déterminer.

Lorsque plusieurs interprétations existent :
- distingue-les clairement ;
- attribue chacune à son auteur ;
- explique les différences essentielles ;
- indique lorsque la conclusion reste discutée.

En cas d'incertitude :
- écris-la dans `incertitudes` ;
- emploie une formulation prudente ;
- n'invente jamais de référence.

SOURCES

Chaque source doit être donnée sous une forme vérifiable :
- auteur ou œuvre ;
- traité, daf, chapitre ou halakha lorsque possible ;
- objet précis de la référence.

Ne donne pas de faux lien Internet.
Une référence traditionnelle précise vaut mieux qu'une URL incertaine.

STYLE

Le français doit être :
- précis ;
- clair ;
- pédagogique ;
- élégant ;
- agréable à lire ;
- adapté à l'étude approfondie.

Réponds uniquement avec l'objet JSON demandé, sans commentaire extérieur.
""".strip()


JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "traduction_fr": {"type": "string"},
        "introduction": {"type": "string"},
        "contexte_general": {"type": "string"},
        "structure_argumentative": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type_etape": {"type": "string"},
                    "texte_concerne": {"type": "string"},
                    "explication": {"type": "string"},
                },
                "required": ["type_etape", "texte_concerne", "explication"],
            },
        },
        "explication_ligne_par_ligne": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "texte_hebreu": {"type": "string"},
                    "mot_a_mot": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "hebreu": {"type": "string"},
                                "translitteration": {"type": "string"},
                                "sens_francais": {"type": "string"},
                                "fonction_dans_la_phrase": {"type": "string"},
                            },
                            "required": [
                                "hebreu",
                                "translitteration",
                                "sens_francais",
                                "fonction_dans_la_phrase",
                            ],
                        },
                    },
                    "traduction_de_la_ligne": {"type": "string"},
                    "explication": {"type": "string"},
                },
                "required": [
                    "texte_hebreu",
                    "mot_a_mot",
                    "traduction_de_la_ligne",
                    "explication",
                ],
            },
        },
        "mots_difficiles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "terme": {"type": "string"},
                    "translitteration": {"type": "string"},
                    "definition": {"type": "string"},
                    "role_dans_le_passage": {"type": "string"},
                },
                "required": [
                    "terme",
                    "translitteration",
                    "definition",
                    "role_dans_le_passage",
                ],
            },
        },
        "notions_nouvelles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notion": {"type": "string"},
                    "explication": {"type": "string"},
                },
                "required": ["notion", "explication"],
            },
        },
        "mefarshim": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "auteur": {"type": "string"},
                    "source": {"type": "string"},
                    "opinion": {"type": "string"},
                    "raisonnement": {"type": "string"},
                    "desaccords": {"type": "string"},
                },
                "required": [
                    "auteur",
                    "source",
                    "opinion",
                    "raisonnement",
                    "desaccords",
                ],
            },
        },
        "halakha_retenue": {"type": "string"},
        "consequences_pratiques": {
            "type": "array",
            "items": {"type": "string"},
        },
        "liens_sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type_source": {"type": "string"},
                    "reference": {"type": "string"},
                    "lien_avec_le_passage": {"type": "string"},
                },
                "required": [
                    "type_source",
                    "reference",
                    "lien_avec_le_passage",
                ],
            },
        },
        "exemples_concrets": {
            "type": "array",
            "items": {"type": "string"},
        },
        "resume_essentiel": {
            "type": "array",
            "items": {"type": "string"},
        },
        "questions_revision": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "question": {"type": "string"},
                    "reponse": {"type": "string"},
                },
                "required": ["question", "reponse"],
            },
        },
        "synthese_finale": {"type": "string"},
        "sources_verifiables": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "auteur_ou_oeuvre": {"type": "string"},
                    "reference": {"type": "string"},
                    "element_verifie": {"type": "string"},
                },
                "required": [
                    "auteur_ou_oeuvre",
                    "reference",
                    "element_verifie",
                ],
            },
        },
        "incertitudes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "traduction_fr",
        "introduction",
        "contexte_general",
        "structure_argumentative",
        "explication_ligne_par_ligne",
        "mots_difficiles",
        "notions_nouvelles",
        "mefarshim",
        "halakha_retenue",
        "consequences_pratiques",
        "liens_sources",
        "exemples_concrets",
        "resume_essentiel",
        "questions_revision",
        "synthese_finale",
        "sources_verifiables",
        "incertitudes",
    ],
}


@dataclass
class Segment:
    node: dict[str, Any]
    path: str
    ref: str
    he: str
    en: str
    rashi: Any = None
    tosafot: Any = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Traduit et enrichit progressivement un traité du Talmud."
    )
    parser.add_argument("--file", required=True, help="Fichier JSON du traité.")
    parser.add_argument("--model", default="gpt-5.5", help="Modèle OpenAI.")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal de segments.")
    parser.add_argument("--force", action="store_true", help="Retraduit les segments déjà traités.")
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Commence au numéro de segment indiqué, base 1.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Nombre maximal de tentatives par segment.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Crée une copie .bak avant le premier changement.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse le fichier sans appeler l'API ni modifier le JSON.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"Fichier introuvable : {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"JSON invalide dans {path}, ligne {exc.lineno}, colonne {exc.colno}: {exc.msg}"
        ) from exc


def atomic_save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(normalize_text(item) for item in value if normalize_text(item))
    return str(value).strip()


def find_first(node: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in node and node[key] not in (None, "", [], {}):
            return node[key]
    return None


def looks_like_segment(node: dict[str, Any]) -> bool:
    he = find_first(
        node,
        (
            "he",
            "hebrew",
            "text_he",
            "heText",
            "textHebrew",
            "heb",
        ),
    )
    if not normalize_text(he):
        return False

    # Évite de traiter comme segment une enveloppe contenant seulement des sous-segments.
    direct_text_keys = {"he", "hebrew", "text_he", "heText", "textHebrew", "heb"}
    return any(key in node for key in direct_text_keys)


def walk_segments(value: Any, path: str = "$") -> Iterator[Segment]:
    if isinstance(value, dict):
        if looks_like_segment(value):
            he = normalize_text(
                find_first(
                    value,
                    ("he", "hebrew", "text_he", "heText", "textHebrew", "heb"),
                )
            )
            en = normalize_text(
                find_first(
                    value,
                    ("en", "english", "text_en", "enText", "textEnglish"),
                )
            )
            ref = normalize_text(
                find_first(
                    value,
                    ("ref", "reference", "id", "title", "name"),
                )
            ) or path

            yield Segment(
                node=value,
                path=path,
                ref=ref,
                he=he,
                en=en,
                rashi=find_first(
                    value,
                    ("rashi", "Rashi", "commentary_rashi", "rashi_comments"),
                ),
                tosafot=find_first(
                    value,
                    ("tosafot", "Tosafot", "commentary_tosafot", "tosafot_comments"),
                ),
            )

        for key, child in value.items():
            yield from walk_segments(child, f"{path}.{key}")

    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_segments(child, f"{path}[{index}]")


def already_done(segment: Segment) -> bool:
    study = segment.node.get("etude_fr")
    if not isinstance(study, dict):
        return False
    translation = normalize_text(study.get("traduction_fr"))
    return bool(translation and normalize_text(segment.node.get("fr")))


def compact_commentary(value: Any, max_chars: int = 12000) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = text.strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n[Commentaire tronqué pour respecter la taille de la requête.]"
    return text


def build_user_prompt(segment: Segment) -> str:
    parts = [
        f"RÉFÉRENCE DU SEGMENT\n{segment.ref}",
        f"TEXTE HÉBREU / ARAMÉEN\n{segment.he}",
    ]

    if segment.en:
        parts.append(
            "TRADUCTION ANGLAISE EXISTANTE\n"
            f"{segment.en}\n\n"
            "Cette traduction anglaise est seulement une aide. "
            "Le texte hébreu/araméen reste la source prioritaire."
        )

    rashi = compact_commentary(segment.rashi)
    if rashi:
        parts.append(
            "RACHI FOURNI DANS LES DONNÉES\n"
            f"{rashi}\n\n"
            "Utilise-le avec précision et ne lui attribue rien qui ne figure pas ici."
        )

    tosafot = compact_commentary(segment.tosafot)
    if tosafot:
        parts.append(
            "TOSSAFOT FOURNIS DANS LES DONNÉES\n"
            f"{tosafot}\n\n"
            "Utilise-les avec précision et distingue clairement leur lecture."
        )

    parts.append(
        "Produis maintenant l'étude complète de ce segment selon le schéma JSON imposé. "
        "Les listes peuvent rester vides lorsqu'un élément n'est pas pertinent ou ne peut "
        "pas être établi avec certitude. N'invente aucune source."
    )
    return "\n\n".join(parts)


def extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    # Compatibilité avec certaines versions du SDK.
    chunks: list[str] = []
    for output in getattr(response, "output", []) or []:
        for content in getattr(output, "content", []) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    result = "\n".join(chunks).strip()
    if not result:
        raise ValueError("La réponse OpenAI ne contient aucun texte exploitable.")
    return result


def call_openai(
    client: OpenAI,
    *,
    model: str,
    segment: Segment,
    max_retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": build_user_prompt(segment),
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "etude_talmud_fr",
                        "strict": True,
                        "schema": JSON_SCHEMA,
                    }
                },
            )

            raw = extract_output_text(response)
            parsed = json.loads(raw)

            if not isinstance(parsed, dict):
                raise ValueError("La réponse structurée n'est pas un objet JSON.")

            translation = normalize_text(parsed.get("traduction_fr"))
            if not translation:
                raise ValueError("Le champ `traduction_fr` est vide.")

            return parsed

        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break

            delay = min(60.0, (2 ** (attempt - 1)) + random.uniform(0.5, 1.5))
            print(
                f"⚠️ Tentative {attempt}/{max_retries} échouée : {exc}",
                file=sys.stderr,
            )
            print(f"   Nouvelle tentative dans {delay:.1f} s…", file=sys.stderr)
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def validate_start(value: int) -> int:
    if value < 1:
        raise SystemExit("--start doit être supérieur ou égal à 1.")
    return value


def main() -> int:
    args = parse_args()
    validate_start(args.start)

    json_path = Path(args.file).expanduser().resolve()
    data = load_json(json_path)
    all_segments = list(walk_segments(data))

    if not all_segments:
        raise SystemExit(
            "Aucun segment contenant un champ hébreu reconnu n'a été trouvé.\n"
            "Champs reconnus : he, hebrew, text_he, heText, textHebrew, heb."
        )

    selected = all_segments[args.start - 1 :]
    if not args.force:
        selected = [segment for segment in selected if not already_done(segment)]

    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit doit être supérieur ou égal à 1.")
        selected = selected[: args.limit]

    print(f"📖 Fichier : {json_path}")
    print(f"   Modèle : {args.model}")
    print(f"   Segments détectés : {len(all_segments)}")
    print(f"   Segments à traiter : {len(selected)}")
    print(f"   Mode forcé : {'oui' if args.force else 'non'}")

    if args.dry_run:
        print("\n🔍 Mode simulation — aucun appel API, aucune modification.")
        for index, segment in enumerate(selected, start=1):
            print(f"   {index}. {segment.ref} — {segment.path}")
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "La variable OPENAI_API_KEY est absente.\n"
            "Exemple Linux : export OPENAI_API_KEY='votre-cle-api'"
        )

    if args.backup:
        backup_path = json_path.with_suffix(json_path.suffix + ".bak")
        shutil.copy2(json_path, backup_path)
        print(f"🛟 Sauvegarde initiale : {backup_path}")

    if not selected:
        print("\n✅ Aucun segment à traduire.")
        return 0

    client = OpenAI()

    for position, segment in enumerate(selected, start=1):
        print(f"\n🔎 {segment.ref}")
        print(f"   Chemin JSON : {segment.path}")

        try:
            study = call_openai(
                client,
                model=args.model,
                segment=segment,
                max_retries=args.max_retries,
            )
        except KeyboardInterrupt:
            print("\n⛔ Interruption demandée. Les segments précédents sont sauvegardés.")
            return 130
        except Exception as exc:
            print(
                f"\n❌ Échec définitif sur {segment.ref} : {exc}",
                file=sys.stderr,
            )
            print(
                "Les segments déjà terminés restent sauvegardés. "
                "Relance la même commande pour reprendre.",
                file=sys.stderr,
            )
            return 1

        translation = normalize_text(study["traduction_fr"])
        segment.node["fr"] = translation
        segment.node["etude_fr"] = study

        atomic_save_json(json_path, data)
        print(f"✅ Sauvegardé ({position}/{len(selected)})")

    print(f"\n✅ Traduction terminée : {len(selected)} segment(s).")
    print(f"   Fichier mis à jour : {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
