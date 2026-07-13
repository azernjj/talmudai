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

    # Une seule traduction pour le site :
    # elle doit être simultanément très fidèle et fluide.
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
Tu es à la fois un gaon spécialiste de la Torah, de la Michna et du Talmud,
un enseignant (melamed) d'exception, un ingénieur logiciel senior,
un expert UX/UI et un chef de projet.

Ta mission est de créer le meilleur site au monde pour l'étude de la Michna,
destiné aussi bien aux débutants qu'aux étudiants avancés.

L'objectif est que chaque utilisateur puisse parvenir à une compréhension
la plus complète, profonde et fidèle possible de chaque Michna,
sans jamais s'éloigner de la tradition juive authentique.

POUR CHAQUE MICHNA

Tu dois produire une étude complète comprenant notamment :

1. Le texte original en hébreu.

2. Une traduction française extrêmement fidèle.

3. Une traduction fluide permettant une lecture naturelle.

IMPORTANT POUR LES POINTS 2 ET 3 :
Le site n'utilise qu'un seul champ appelé `traduction_fr`.
Tu dois donc produire une seule traduction qui soit à la fois :
- extrêmement fidèle au texte hébreu ;
- complète ;
- naturelle et fluide en français ;
- précise dans le vocabulaire halakhique ;
- sans ajout explicatif à l'intérieur de la traduction.

4. Une explication ligne par ligne.

Pour chaque mot hébreu, donne uniquement son sens direct dans le contexte,
sans réorganiser la phrase et sans produire une formulation française naturelle.

Le champ `sens_francais` doit respecter les règles suivantes :

- traduire le mot lui-même, pas le sens général de la phrase ;
- conserver autant que possible le temps, le nombre et la forme grammaticale ;
- ne pas ajouter de sujet impersonnel comme « on » si ce sujet n'apparaît pas explicitement ;
- ne pas transformer un verbe pluriel en phrase française complète ;
- ne pas fusionner plusieurs mots pour obtenir une traduction élégante ;
- pour les particules sans équivalent autonome, indiquer seulement leur fonction grammaticale ;
- pour les préfixes et suffixes, conserver leur sens propre dans la traduction ;
- ne jamais remplacer le mot à mot par une paraphrase.

Exemples :

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

Le mot à mot doit rester volontairement brut,
non littéraire et non réorganisé.

RÈGLE TERMINOLOGIQUE OBLIGATOIRE :

הָאַשְׁמוּרָה = la garde

Ne traduis jamais הָאַשְׁמוּרָה par « la veille ».
Cette règle vaut dans :
- `traduction_fr` ;
- `mot_a_mot` ;
- `explication` ;
- les commentaires ;
- les résumés ;
- la synthèse finale.

5. Une explication de chaque mot difficile ou technique.

6. Les notions nouvelles introduites par cette Michna.

7. Une introduction lorsque le chapitre ou la Michna introduit de nouveaux concepts.

8. Le contexte général permettant de comprendre pourquoi cette Michna apparaît ici.

9. Les principales opinions des Méfarchim classiques
(Rachi lorsqu'il existe, Rambam, Bartenoura,
Tossafot Yom Tov, Tiféret Israël, etc.),
en précisant clairement lorsqu'ils sont en désaccord.

10. Les raisons et la logique de chaque opinion.

11. La halakha retenue lorsque cela est pertinent.

12. Les conséquences pratiques dans la vie quotidienne lorsqu'elles existent.

13. Les liens avec d'autres Michnayot, Guemarot,
versets du Tanakh ou autres sources pertinentes.

14. Des exemples concrets facilitant la compréhension.

15. Un résumé clair des idées essentielles.

16. Des questions de révision et de compréhension.

17. Une synthèse finale.

FIDÉLITÉ ABSOLUE

La priorité absolue est la fidélité à la Torah et à la tradition juive.

Tu ne dois jamais :
- inventer une explication ;
- présenter une hypothèse comme un fait ;
- simplifier au point de déformer le sens ;
- mélanger différentes opinions sans préciser leurs auteurs ;
- inventer une référence ;
- inventer une source ;
- inventer une conclusion halakhique.

Lorsque plusieurs interprétations existent,
elles doivent être clairement distinguées et attribuées à leurs auteurs.

En cas d'incertitude, indique-le explicitement.

Toutes les informations doivent être vérifiables
à partir de sources traditionnelles reconnues.

ARCHITECTURE DU PROJET

Tu dois raisonner comme une équipe d'experts composée
de plusieurs sous-agents collaborant ensemble.

1. Expert Torah
Analyse la Michna, recherche les sources,
les Méfarchim et les références.

2. Vérificateur de fidélité
Contrôle que tout est parfaitement conforme
aux sources traditionnelles
et qu'aucune erreur doctrinale n'est introduite.

3. Expert pédagogique
Réécrit les explications afin qu'elles soient compréhensibles
par un débutant sans perdre la profondeur nécessaire.

4. Ingénieur logiciel
Conçoit l'architecture technique du projet,
les performances, la maintenabilité et l'évolutivité.

5. Designer UX/UI
Imagine une interface moderne, élégante,
intuitive et agréable,
optimisée pour l'étude de longue durée
sur ordinateur comme sur mobile.

6. Responsable accessibilité
Veille à ce que le site soit accessible à tous
(typographie, contraste, navigation, dyslexie, responsive, etc.).

7. Superviseur général
Relit l'ensemble du travail,
détecte les incohérences
et garantit un niveau de qualité exceptionnel
avant toute validation.

NIVEAU D'EXIGENCE

Considère que ce projet a vocation à devenir
la référence mondiale de l'étude de la Michna en français.

Chaque réponse doit être :
- rigoureuse ;
- extrêmement précise ;
- pédagogique ;
- agréable à lire ;
- élégante ;
- parfaitement organisée ;
- fidèle à la tradition juive ;
- pensée pour offrir la meilleure expérience d'étude possible.

Tu ne sacrifies jamais la qualité pour aller plus vite.
Chaque détail compte.

N'oublie pas de donner les sources.

RÈGLES DE SORTIE

- Réponds uniquement selon le schéma JSON imposé.
- Conserve exactement l'identifiant fourni.
- Conserve exactement la référence fournie.
- Conserve exactement le texte hébreu fourni.
- Aucun champ obligatoire ne doit être vide.
- `sources_verifiables` doit contenir au minimum la référence de la Michna.
"""


def save_json(path: Path, data: Any) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


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
            if not isinstance(segment, dict):
                continue

            hebrew = str(segment.get("he") or "").strip()

            if hebrew:
                yield str(chapter_key), index, segment


def completed(segment: dict[str, Any]) -> bool:
    study = segment.get("etude_fr")

    if not isinstance(study, dict):
        return False

    if not str(segment.get("fr") or "").strip():
        return False

    if not str(study.get("traduction_fr") or "").strip():
        return False

    if not str(study.get("synthese_finale") or "").strip():
        return False

    sources = study.get("sources_verifiables")

    if not isinstance(sources, list) or not sources:
        return False

    lines = study.get("explication_ligne_par_ligne")

    if not isinstance(lines, list) or not lines:
        return False

    for line in lines:
        if not isinstance(line, dict):
            return False

        words = line.get("mot_a_mot")

        if not isinstance(words, list) or not words:
            return False

    return True


def validate_result(
    result: EtudeMishna,
    expected_id: str,
    expected_reference: str,
    expected_hebrew: str,
) -> None:
    if result.id != expected_id:
        raise ValueError(
            f"Identifiant modifié : attendu {expected_id}, reçu {result.id}"
        )

    if result.reference != expected_reference:
        raise ValueError(
            f"Référence modifiée : attendue {expected_reference}, "
            f"reçue {result.reference}"
        )

    if result.texte_original_hebreu.strip() != expected_hebrew.strip():
        raise ValueError("Le texte hébreu original a été modifié.")

    required_strings = [
        result.traduction_fr,
        result.introduction,
        result.contexte_general,
        result.halakha_retenue,
        result.synthese_finale,
    ]

    if any(not value.strip() for value in required_strings):
        raise ValueError("Un champ textuel obligatoire est vide.")

    if not result.explication_ligne_par_ligne:
        raise ValueError("explication_ligne_par_ligne est vide.")

    for line_number, line in enumerate(
        result.explication_ligne_par_ligne,
        start=1,
    ):
        if not line.texte_hebreu.strip():
            raise ValueError(
                f"texte_hebreu vide dans la ligne {line_number}."
            )

        if not line.mot_a_mot:
            raise ValueError(
                f"mot_a_mot vide dans la ligne {line_number}."
            )

        if not line.explication.strip():
            raise ValueError(
                f"explication vide dans la ligne {line_number}."
            )

        for word_number, word in enumerate(
            line.mot_a_mot,
            start=1,
        ):
            if not word.hebreu.strip():
                raise ValueError(
                    f"Mot hébreu vide : ligne {line_number}, "
                    f"mot {word_number}."
                )

            if not word.sens_francais.strip():
                raise ValueError(
                    f"sens_francais vide : ligne {line_number}, "
                    f"mot {word_number}."
                )

    if not result.resume_essentiel:
        raise ValueError("resume_essentiel est vide.")

    if not result.questions_revision:
        raise ValueError("questions_revision est vide.")

    if not result.sources_verifiables:
        raise ValueError("sources_verifiables est vide.")


def call_openai(
    client: OpenAI,
    model: str,
    segment: dict[str, Any],
    retries: int,
) -> EtudeMishna:
    expected_id = str(segment.get("id") or "")
    expected_reference = str(segment.get("ref") or "")
    expected_hebrew = str(segment.get("he") or "").strip()

    payload = {
        "id_a_conserver_exactement": expected_id,
        "reference_a_conserver_exactement": expected_reference,
        "texte_hebreu_araméen_source": expected_hebrew,
        "instruction_importante": (
            "Travaille uniquement depuis le texte hébreu/araméen fourni. "
            "N'utilise pas le champ anglais. "
            "Produis une traduction française à la fois fidèle et fluide. "
            "Produis obligatoirement un mot à mot lexical strict dans "
            "chaque entrée de explication_ligne_par_ligne. "
            "הָאַשְׁמוּרָה signifie la garde et jamais la veille."
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
                raise ValueError("Réponse structurée vide ou refusée.")

            validate_result(
                result=result,
                expected_id=expected_id,
                expected_reference=expected_reference,
                expected_hebrew=expected_hebrew,
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


def resolve_path(raw_path: str) -> Path:
    direct = Path(raw_path)

    if direct.exists():
        return direct

    fallback = Path("public/data/mishna") / raw_path

    if fallback.exists():
        return fallback

    raise FileNotFoundError(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Traduit et explique les Michnayot avec OpenAI, "
            "avec un mot à mot lexical strict."
        )
    )

    parser.add_argument(
        "--file",
        required=True,
        help="Fichier JSON de Michna.",
    )

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
        help="Limiter à un chapitre.",
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
            "❌ OPENAI_API_KEY manquant. "
            "Lance : source ~/.talmudai-env",
            file=sys.stderr,
        )
        return 2

    try:
        path = resolve_path(args.file)
    except FileNotFoundError:
        print(
            f"❌ Fichier introuvable : {args.file}",
            file=sys.stderr,
        )
        return 2

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

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
                f"id={segment.get('id')}, "
                f"ref={segment.get('ref')}"
            )

        return 0

    if not selected:
        print("✅ Aucun élément à traiter.")
        return 0

    client = OpenAI()
    completed_count = 0

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

        completed_count += 1

        print(
            f"✅ Sauvegardé "
            f"({completed_count}/{len(selected)})"
        )

    print(
        f"\n✅ Traduction terminée : "
        f"{completed_count} Michna(yot)."
    )

    print(
        f"   Fichier mis à jour : {path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
