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


class MotAMot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hebreu: str
    translitteration: str
    sens_francais: str
    fonction_dans_la_phrase: str


class LigneExpliquee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texte_hebreu: str
    mot_a_mot: list[MotAMot]
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
Produire, pour une seule Michna :
1. une traduction française unique, fidèle et fluide ;
2. un véritable mot à mot lexical brut ;
3. une étude complète, pédagogique et strictement fidèle aux sources traditionnelles.

LANGUE SOURCE
- Travaille directement depuis le texte hébreu/araméen fourni.
- N'utilise jamais l'anglais comme base.
- Ignore toute traduction anglaise éventuellement présente dans le fichier.

TRADUCTION FRANÇAISE UNIQUE
Produis une seule traduction française dans `traduction_fr`.

Cette traduction doit être :
- extrêmement fidèle au texte hébreu ou araméen ;
- complète, sans omission ;
- précise dans le vocabulaire halakhique ;
- naturelle et fluide en français ;
- lisible sans déformer le sens.

Ne produis pas de deuxième traduction littéraire ou fidèle séparée.
Les explications doivent rester dans les champs d'étude.

MOT À MOT LEXICAL STRICT
Pour chaque ligne ou unité de sens :
- recopie exactement le texte hébreu dans `texte_hebreu` ;
- produis dans `mot_a_mot` une entrée séparée pour chaque mot hébreu,
  ou pour chaque unité grammaticale minimale réellement inséparable.

Pour chaque entrée de `mot_a_mot`, indique :
- `hebreu` : le mot exact en hébreu, avec préfixes et suffixes ;
- `translitteration` : sa prononciation ;
- `sens_francais` : le sens lexical direct du mot dans ce contexte ;
- `fonction_dans_la_phrase` : sa fonction grammaticale précise.

Règles obligatoires pour `sens_francais` :
- traduire le mot lui-même et non le sens général de la phrase ;
- conserver autant que possible le temps, le nombre, la personne et la forme grammaticale ;
- ne pas réorganiser les mots pour former une phrase française naturelle ;
- ne pas ajouter un sujet comme « on », « il » ou « ils » s'il n'apparaît pas explicitement ;
- ne pas fusionner plusieurs mots pour rendre la traduction élégante ;
- ne pas transformer un pluriel en singulier ;
- ne pas transformer un verbe en nom ;
- ne pas ajouter d'explication dans `sens_francais` ;
- pour une particule sans équivalent autonome, indiquer seulement sa fonction grammaticale ;
- pour les préfixes et suffixes, conserver leur valeur directe dans le sens lexical ;
- placer toute précision grammaticale dans `fonction_dans_la_phrase`.

Exemples corrects :
מֵאֵימָתַי
sens_francais : "depuis quand"

קוֹרִין
sens_francais : "lisent / récitent"
fonction_dans_la_phrase : "verbe, troisième personne du pluriel, emploi impersonnel dans le contexte"

אֶת
sens_francais : "marque du complément d'objet direct"
fonction_dans_la_phrase : "particule grammaticale sans traduction autonome"

שְׁמַע
sens_francais : "Chéma"

בְּעַרְבִית
sens_francais : "au soir / dans le soir"
fonction_dans_la_phrase : "complément de temps avec préfixe ב"

Exemples interdits :
קוֹרִין = "on récite"
מֵאֵימָתַי קוֹרִין = "à partir de quand récite-t-on"
בְּעַרְבִית = "le soir" sans rendre ni expliquer le préfixe ב

Le mot à mot doit rester volontairement brut, non littéraire et non réorganisé.

FIDÉLITÉ ABSOLUE
- N'invente aucune source, opinion, halakha ou référence.
- Ne présente jamais une hypothèse comme un fait.
- Distingue clairement les auteurs et les opinions.
- Si une attribution est incertaine, omets-la de `mefarshim`
  et signale-la dans `incertitudes`.
- Si la halakha pratique ne peut pas être vérifiée avec certitude, écris :
  "À vérifier dans les sources halakhiques faisant autorité."
- Conserve exactement l'identifiant, la référence et le texte hébreu fournis.
- En cas de doute sérieux sur un terme, conserve la translittération et ajoute [?].
- Réponds uniquement selon le schéma JSON demandé.

CONTENU OBLIGATOIRE
- une traduction française unique, fidèle et fluide ;
- un mot à mot lexical strict, mot par mot, non réorganisé ;
- une explication ligne par ligne ;
- une introduction ;
- le contexte général ;
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
            if (
                isinstance(segment, dict)
                and str(segment.get("he") or "").strip()
            ):
                yield str(chapter_key), index, segment


def completed(segment: dict[str, Any]) -> bool:
    study = segment.get("etude_fr")

    if not (
        str(segment.get("fr") or "").strip()
        and isinstance(study, dict)
        and str(study.get("traduction_fr") or "").strip()
        and str(study.get("synthese_finale") or "").strip()
        and isinstance(study.get("sources_verifiables"), list)
        and study.get("sources_verifiables")
    ):
        return False

    lines = study.get("explication_ligne_par_ligne")

    if not isinstance(lines, list) or not lines:
        return False

    return all(
        isinstance(line, dict)
        and isinstance(line.get("mot_a_mot"), list)
        and line.get("mot_a_mot")
        for line in lines
    )


def validate_result(
    result: EtudeMishna,
    expected_id: str,
    expected_ref: str,
    expected_he: str,
) -> None:
    if result.id != expected_id:
        raise ValueError(
            f"Identifiant modifié : attendu {expected_id}, reçu {result.id}"
        )

    if result.reference != expected_ref:
        raise ValueError(
            f"Référence modifiée : attendue {expected_ref}, reçue {result.reference}"
        )

    if result.texte_original_hebreu.strip() != expected_he.strip():
        raise ValueError("Le texte hébreu original a été modifié.")

    if not result.traduction_fr.strip():
        raise ValueError("traduction_fr est vide.")

    if not result.introduction.strip():
        raise ValueError("introduction est vide.")

    if not result.contexte_general.strip():
        raise ValueError("contexte_general est vide.")

    if not result.explication_ligne_par_ligne:
        raise ValueError("explication_ligne_par_ligne est vide.")

    for line_index, line in enumerate(
        result.explication_ligne_par_ligne,
        start=1,
    ):
        if not line.texte_hebreu.strip():
            raise ValueError(
                f"texte_hebreu vide dans la ligne {line_index}."
            )

        if not line.mot_a_mot:
            raise ValueError(
                f"mot_a_mot vide dans la ligne {line_index}."
            )

        for word_index, word in enumerate(
            line.mot_a_mot,
            start=1,
        ):
            if not word.hebreu.strip():
                raise ValueError(
                    f"Mot hébreu vide : ligne {line_index}, mot {word_index}."
                )

            if not word.sens_francais.strip():
                raise ValueError(
                    f"sens_francais vide : ligne {line_index}, mot {word_index}."
                )

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
            "Produis une traduction française unique, fidèle et fluide. "
            "Produis aussi un vrai mot à mot lexical brut, mot par mot, "
            "sans réorganiser la phrase. N'utilise pas le champ anglais."
        ),
    }

    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = client.responses.parse(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            payload,
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ],
                text_format=EtudeMishna,
            )

            result = response.output_parsed

            if result is None:
                raise ValueError("Réponse structurée vide.")

            validate_result(
                result,
                expected_id,
                expected_ref,
                expected_he,
            )

            return result

        except Exception as exc:
            last_error = exc

            print(
                f"⚠️ Tentative {attempt}/{retries} échouée : {exc}",
                file=sys.stderr,
            )

            if attempt < retries:
                time.sleep(min(2 ** attempt, 20))

    raise RuntimeError(f"Échec définitif : {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Traduit et explique les Michnayot avec une traduction "
            "française unique et un mot à mot lexical strict."
        )
    )

    parser.add_argument("--file", required=True)

    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_MODEL", "gpt-5.5"),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="0 = toutes les Michnayot restantes.",
    )

    parser.add_argument(
        "--chapter",
        default="",
        help="Limiter à un chapitre précis.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Regénérer les Michnayot déjà terminées.",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher la sélection sans appel API.",
    )

    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print(
            "❌ OPENAI_API_KEY manquant. Lance : source ~/.talmudai-env",
            file=sys.stderr,
        )
        return 2

    path = Path(args.file)

    if not path.exists():
        fallback = Path("public/data/mishna") / args.file

        if fallback.exists():
            path = fallback
        else:
            print(
                f"❌ Fichier introuvable : {args.file}",
                file=sys.stderr,
            )
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
        selected = selected[:args.limit]

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
        print(
            f"\n🔎 {segment.get('ref')} "
            f"(chapitre {chapter}, index {index})"
        )

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
