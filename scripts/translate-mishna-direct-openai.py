#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict


class LigneExpliquee(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texte_hebreu: str
    traduction_fr: str
    explication: str


class MotDifficile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mot: str
    translitteration: str
    traduction: str
    explication: str


class OpinionMefarech(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auteur: str
    source_precise: str
    opinion: str
    logique: str
    desaccords: str


class LienSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str
    type_source: str
    explication_du_lien: str


class QuestionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    reponse_attendue: str


class EtudeMishna(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    reference: str
    texte_original_hebreu: str
    traduction_fr: str
    introduction: str
    contexte_general: str
    explication_ligne_par_ligne: list[LigneExpliquee]
    mots_difficiles: list[MotDifficile]
    notions_nouvelles: list[str]
    mefarshim: list[OpinionMefarech]
    halakha_retenue: str
    consequences_pratiques: list[str]
    liens_sources: list[LienSource]
    exemples_concrets: list[str]
    resume_essentiel: list[str]
    questions_revision: list[QuestionRevision]
    synthese_finale: str
    sources_verifiables: list[str]
    incertitudes: list[str]


SYSTEM_PROMPT = r"""
Tu es un spécialiste rigoureux de la Torah, de la Michna et du Talmud,
un melamed expérimenté et un vérificateur de fidélité aux sources classiques.

MISSION
Produire, pour une seule Michna, une traduction française unique et une étude complète.

LANGUE SOURCE
- Travaille directement depuis le texte hébreu/araméen fourni.
- N'utilise jamais l'anglais comme base.
- N'utilise aucune traduction anglaise éventuellement présente dans le fichier.

TRADUCTION FRANÇAISE UNIQUE
Produis une seule traduction française dans le champ `traduction_fr`.

Cette traduction doit être simultanément :
- extrêmement fidèle au texte hébreu ou araméen ;
- complète, sans omission ;
- fluide et naturelle en français ;
- précise dans le vocabulaire halakhique ;
- fidèle à la structure logique de la Michna ;
- lisible par un débutant sans déformer le sens.

Ne produis pas une traduction littérale séparée et une traduction fluide séparée.
N'ajoute pas d'explications dans la traduction elle-même.
Les explications doivent apparaître uniquement dans les champs d'étude prévus.

FIDÉLITÉ ABSOLUE
- N'invente aucune source, opinion, halakha ou référence.
- Ne présente jamais une hypothèse comme un fait.
- Distingue clairement les auteurs et les opinions.
- Si une attribution est incertaine, omets-la de `mefarshim` et signale-la dans `incertitudes`.
- Si la halakha pratique ne peut pas être vérifiée avec certitude, écris :
  "À vérifier dans les sources halakhiques faisant autorité."
- Conserve exactement l'identifiant, la référence et le texte hébreu fournis.
- En cas de doute sérieux sur un terme, conserve la translittération et ajoute [?].
- Réponds uniquement selon le schéma JSON demandé.

CONTENU OBLIGATOIRE
- une traduction française unique, fidèle, précise et fluide ;
- une introduction ;
- le contexte général ;
- une explication ligne par ligne ;
- les mots difficiles et techniques ;
- les notions nouvelles ;
- les opinions classiques pertinentes et vérifiables ;
- la logique de chaque opinion ;
- les désaccords éventuels ;
- la halakha retenue si elle est vérifiable ;
- les conséquences pratiques ;
- les liens avec d'autres Michnayot, Guemarot, versets et sources ;
- des exemples concrets ;
- un résumé essentiel ;
- des questions de révision avec réponses ;
- une synthèse finale ;
- les sources vérifiables ;
- les incertitudes.

HARMONISATION TALMUDIQUE
מתניתין = notre Michna / la Michna
תנן = nous avons appris dans une Michna
תניא = il a été enseigné dans une baraïta
תנו רבנן = les Sages ont enseigné
מאי טעמא = pour quelle raison ?
מנא הני מילי = d'où savons-nous cela ?
פשיטא = c'est évident
קא משמע לן = cela vient nous enseigner
איבעיא להו = une question leur fut posée
תיקו = la question reste non résolue (teïkou)
תא שמע = viens et écoute une preuve
שמע מינה = déduis-en que
איתיביה = il lui objecta
מתקיף לה = il souleva une objection
לא קשיא = ce n'est pas une difficulté
הכא במאי עסקינן = de quel cas traitons-nous ici ?
אלא = mais plutôt / en réalité
אי הכי = s'il en est ainsi
נפקא מינה = conséquence pratique
קשיא = la difficulté demeure
תיובתא = réfutation décisive
הלכתא = la halakha est

VOCABULAIRE
אסור = interdit
מותר = permis
חייב = est tenu de / est passible de / est redevable de, selon le contexte
פטור = exempt / dispensé / non passible
טמא = impur rituellement
טהור = pur rituellement
קנין = acte d'acquisition juridique (kinyan)
חזקה = présomption juridique / possession établie / mode d'acquisition (‘hazaka)
הפקר = bien sans propriétaire (hefker)
ממון = obligation ou valeur monétaire
קנס = amende légale
נזק = dommage
לכתחילה = a priori
בדיעבד = a posteriori
דרבנן = d'ordre rabbinique
דאורייתא = d'ordre toranique
גט = guet
כתובה = ketouba
קידושין = kiddouchin
יבום = yiboum
חליצה = ‘halitsa
"""


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def iter_mishnayot(data: dict[str, Any]):
    chapters = data.get("chapters") or {}

    if isinstance(chapters, dict):
        chapter_items = chapters.items()
    elif isinstance(chapters, list):
        chapter_items = enumerate(chapters, start=1)
    else:
        raise ValueError("Champ `chapters` absent ou invalide.")

    for chapter_key, chapter in chapter_items:
        if not isinstance(chapter, dict):
            continue

        mishnayot = chapter.get("mishnayot") or chapter.get("mishnah") or []
        if not isinstance(mishnayot, list):
            continue

        for index, segment in enumerate(mishnayot):
            if isinstance(segment, dict) and str(segment.get("he") or "").strip():
                yield str(chapter_key), index, segment


def completed(segment: dict[str, Any]) -> bool:
    study = segment.get("etude_fr")
    return bool(
        str(segment.get("fr") or "").strip()
        and isinstance(study, dict)
        and str(study.get("traduction_fr") or "").strip()
        and str(study.get("synthese_finale") or "").strip()
        and isinstance(study.get("sources_verifiables"), list)
        and study.get("sources_verifiables")
    )


def validate_result(
    result: EtudeMishna,
    expected_id: str,
    expected_ref: str,
    expected_he: str,
) -> None:
    if result.id != expected_id:
        raise ValueError(f"Identifiant modifié : attendu {expected_id}, reçu {result.id}")
    if result.reference != expected_ref:
        raise ValueError(f"Référence modifiée : attendue {expected_ref}, reçue {result.reference}")
    if result.texte_original_hebreu.strip() != expected_he.strip():
        raise ValueError("Le texte hébreu original a été modifié.")
    if not result.traduction_fr.strip():
        raise ValueError("traduction_fr est vide.")
    if not result.explication_ligne_par_ligne:
        raise ValueError("explication_ligne_par_ligne est vide.")
    if not result.resume_essentiel:
        raise ValueError("resume_essentiel est vide.")
    if not result.questions_revision:
        raise ValueError("questions_revision est vide.")
    if not result.synthese_finale.strip():
        raise ValueError("synthese_finale est vide.")
    if not result.sources_verifiables:
        raise ValueError("sources_verifiables est vide.")


def call_openai(
    client: OpenAI,
    model: str,
    segment: dict[str, Any],
    retries: int,
) -> EtudeMishna:
    expected_id = str(segment.get("id") or "")
    expected_ref = str(segment.get("ref") or "")
    expected_he = str(segment.get("he") or "").strip()

    payload = {
        "id_a_conserver_exactement": expected_id,
        "reference_a_conserver_exactement": expected_ref,
        "texte_hebreu_araméen_source": expected_he,
        "instruction": (
            "Travaille uniquement depuis le texte hébreu/araméen. "
            "Produis une seule traduction française, à la fois fidèle et fluide. "
            "N'utilise pas le champ anglais."
        ),
    }

    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False, indent=2),
                    },
                ],
                text_format=EtudeMishna,
            )

            result = response.output_parsed
            if result is None:
                raise ValueError("Réponse structurée vide.")

            validate_result(result, expected_id, expected_ref, expected_he)
            return result

        except Exception as exc:
            last_error = exc
            print(f"⚠️ Tentative {attempt}/{retries} échouée : {exc}", file=sys.stderr)
            if attempt < retries:
                time.sleep(min(2 ** attempt, 20))

    raise RuntimeError(f"Échec définitif : {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Traduit et explique les Michnayot avec une traduction française unique."
    )
    parser.add_argument("--file", required=True)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--chapter", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY manquant. Lance : source ~/.talmudai-env", file=sys.stderr)
        return 2

    path = Path(args.file)
    if not path.exists():
        fallback = Path("public/data/mishna") / args.file
        if fallback.exists():
            path = fallback
        else:
            print(f"❌ Fichier introuvable : {args.file}", file=sys.stderr)
            return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = list(iter_mishnayot(data))
    selected = []

    for chapter, index, segment in candidates:
        if args.chapter and chapter != args.chapter:
            continue
        if not args.force and completed(segment):
            continue
        selected.append((chapter, index, segment))

    if args.limit > 0:
        selected = selected[: args.limit]

    print(f"📖 Fichier : {path}")
    print(f"   Modèle : {args.model}")
    print(f"   Michnayot détectées : {len(candidates)}")
    print(f"   Michnayot à traiter : {len(selected)}")

    if args.dry_run:
        for chapter, index, segment in selected:
            print(
                f"- chapitre {chapter}, index {index}, "
                f"id={segment.get('id')}, ref={segment.get('ref')}"
            )
        return 0

    if not selected:
        print("✅ Aucun élément à traiter.")
        return 0

    client = OpenAI()
    done = 0

    for chapter, index, segment in selected:
        print(f"\n🔎 {segment.get('ref')} (chapitre {chapter}, index {index})")

        result = call_openai(
            client=client,
            model=args.model,
            segment=segment,
            retries=max(1, args.retries),
        )

        segment["fr"] = result.traduction_fr
        segment["etude_fr"] = result.model_dump(mode="json")
        save_json(path, data)

        done += 1
        print(f"✅ Sauvegardé ({done}/{len(selected)})")

    print(f"\n✅ Traduction terminée : {done} Michna(yot).")
    print(f"   Fichier mis à jour : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
