#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine_v7_2.aligned_commentaries import (
    AlignedCommentaryLibrary,
)
from engine_v7_2.aligned_translator import (
    AlignedTranslator,
)
from engine_v7_2.aligned_quality import (
    ReviewQueue,
    analyse_translation,
)
from engine_v7_2.aligned_writer import (
    apply_aligned_translation,
    save_document_atomic,
)
from engine_v7_2.budget import (
    BudgetError,
    BudgetGuard,
)
from engine_v7_2.english_source import (
    EnglishSourceLibrary,
)
from engine_v7_2.openai_client import (
    OpenAIEngineError,
    ResponsesJsonClient,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "TALMUD AI V7.2 — traduction française "
            "depuis le corpus anglais aligné, avec Rachi "
            "et Tossefot exactement associés."
        )
    )

    parser.add_argument(
        "--project-root",
        default=".",
        help="Racine du projet TALMUD AI.",
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Fichier merged du traité à modifier.",
    )
    parser.add_argument(
        "--only-daf",
        required=True,
        help="Daf à traiter, par exemple 2b.",
    )
    parser.add_argument(
        "--start-segment",
        type=int,
        default=1,
        help="Premier segment humain, à partir de 1.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help=(
            "Nombre maximal de segments à traiter. "
            "Utiliser 0 pour aller jusqu’à la fin du daf."
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Force un modèle unique pour tous les segments. "
            "Sans cette option, le choix est automatique."
        ),
    )
    parser.add_argument(
        "--model-main",
        default="gpt-5-mini",
        help=(
            "Modèle utilisé pour le texte principal et les "
            "commentaires disposant déjà d'un anglais aligné."
        ),
    )
    parser.add_argument(
        "--model-hebrew",
        default="gpt-5-mini",
        help=(
            "Modèle utilisé lorsqu'un commentaire doit être "
            "compris directement depuis l'hébreu."
        ),
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=1400,
        help="Sortie maximale par segment.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remplace une traduction française existante.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Contrôle les sources sans appel API ni écriture.",
    )

    return parser


def load_document(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise TypeError(
            "Le fichier merged doit contenir un objet JSON."
        )

    dapim = payload.get("dapim")

    if not isinstance(dapim, dict):
        raise ValueError(
            "Le fichier merged ne contient pas de dictionnaire dapim."
        )

    return payload


def get_segments(
    document: dict[str, Any],
    daf: str,
) -> list[dict[str, Any]]:
    daf_payload = document["dapim"].get(daf)

    if not isinstance(daf_payload, dict):
        raise ValueError(
            f"Le daf {daf} est absent du fichier merged."
        )

    segments = daf_payload.get("segments")

    if not isinstance(segments, list):
        raise ValueError(
            f"La liste des segments de {daf} est absente."
        )

    return segments


def choose_model(
    *,
    forced_model: str | None,
    main_model: str,
    hebrew_model: str,
    commentaries: dict[str, list[Any]],
) -> tuple[str, str]:
    """
    Choisit le modèle le moins coûteux compatible avec les sources.

    Un modèle plus puissant n'est utilisé que lorsqu'un commentaire
    doit être compris directement depuis l'hébreu.
    """
    if forced_model:
        return forced_model, "modèle forcé"

    for entries in commentaries.values():
        for entry in entries:
            has_hebrew = bool(
                str(getattr(entry, "hebrew", "") or "").strip()
            )
            has_english = bool(
                str(getattr(entry, "english", "") or "").strip()
            )

            if has_hebrew and not has_english:
                return (
                    hebrew_model,
                    "commentaire hébreu sans anglais",
                )

    return (
        main_model,
        "texte principal ou commentaire anglais",
    )


def budget_metadata(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, Any]:
    return {
        "translator_model": model,
        "reviewer_model": None,
        "tokens": {
            "translator": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens,
            },
            "reviewer": {
                "input": 0,
                "output": 0,
                "total": 0,
            },
        },
    }


def main() -> int:
    args = build_parser().parse_args()

    project_root = Path(
        args.project_root
    ).resolve()

    corpus_path = Path(args.file)

    if not corpus_path.is_absolute():
        corpus_path = project_root / corpus_path

    corpus_path = corpus_path.resolve()

    if not corpus_path.exists():
        print(
            f"❌ Fichier introuvable : {corpus_path}",
            file=sys.stderr,
        )
        return 2

    masechet = corpus_path.stem.lower()
    daf = str(args.only_daf).strip().lower()

    if args.start_segment < 1:
        print(
            "❌ --start-segment doit être supérieur ou égal à 1.",
            file=sys.stderr,
        )
        return 2

    if args.limit < 0:
        print(
            "❌ --limit ne peut pas être négatif.",
            file=sys.stderr,
        )
        return 2

    try:
        document = load_document(corpus_path)
        segments = get_segments(document, daf)

        source_library = EnglishSourceLibrary(
            project_root,
            masechet,
        )

        commentary_library = AlignedCommentaryLibrary(
            project_root,
            masechet,
        )

        budget = BudgetGuard(project_root)
        review_queue = ReviewQueue(project_root)

    except Exception as exc:
        print(f"❌ Initialisation impossible : {exc}")
        return 1

    start_index = args.start_segment - 1

    if start_index >= len(segments):
        print(
            f"❌ Segment {args.start_segment} hors limites : "
            f"{daf} contient {len(segments)} segments."
        )
        return 2

    if args.limit == 0:
        end_index = len(segments)
    else:
        end_index = min(
            len(segments),
            start_index + args.limit,
        )

    print("=" * 60)
    print(" TALMUD AI — TRADUCTION ALIGNÉE V7.2")
    print("=" * 60)
    print(f"Corpus : {corpus_path}")
    print(f"Traité : {masechet}")
    print(f"Daf : {daf}")
    print(
        "Segments demandés : "
        f"{start_index + 1} à {end_index}"
    )
    if args.model:
        print(f"Modèle forcé : {args.model}")
    else:
        print(
            "Modèles automatiques : "
            f"principal={args.model_main}, "
            f"hébreu={args.model_hebrew}"
        )
    print(
        "Budget dépensé : "
        f"{budget.spent_eur:.6f} €"
    )
    print(
        "Budget restant : "
        f"{budget.remaining_eur:.6f} €"
    )

    if args.dry_run:
        print("\n🔎 Contrôle des sources")

        for index in range(start_index, end_index):
            number = index + 1

            source = source_library.load_segment(
                daf,
                number,
            )
            commentaries = commentary_library.for_segment(
                daf,
                number,
            )

            print(
                f"  {source.base_ref} : "
                f"anglais={len(source.english)} caractères, "
                f"Rachi={len(commentaries['rachi'])}, "
                f"Tossefot={len(commentaries['tossefot'])}"
            )

        print(
            "\n✅ Dry-run terminé : "
            "aucun appel API, aucune modification."
        )
        return 0

    client = ResponsesJsonClient(
        json_attempts=2,
    )

    saved = 0
    skipped = 0
    run_cost = 0.0
    run_tokens = 0
    failures: list[dict[str, object]] = []

    for index in range(start_index, end_index):
        number = index + 1
        segment = segments[index]

        print(
            f"\n🔎 Traitement de {masechet} "
            f"{daf}:{number}"
        )

        if (
            not args.force
            and isinstance(segment.get("fr"), str)
            and segment["fr"].strip()
        ):
            print(
                "⏭️ Traduction française déjà présente : "
                "segment ignoré."
            )
            skipped += 1
            continue

        selected_model = (
            args.model
            or args.model_main
        )

        try:
            budget.ensure_call_allowed()

            source = source_library.load_segment(
                daf,
                number,
            )

            commentaries = commentary_library.for_segment(
                daf,
                number,
            )

            selected_model, model_reason = choose_model(
                forced_model=args.model,
                main_model=args.model_main,
                hebrew_model=args.model_hebrew,
                commentaries=commentaries,
            )

            print(
                "📚 Sources alignées : "
                f"Rachi={len(commentaries['rachi'])}, "
                f"Tossefot={len(commentaries['tossefot'])}"
            )
            print(
                f"🤖 Modèle : {selected_model} "
                f"({model_reason})"
            )

            translator = AlignedTranslator(
                client=client,
                model=selected_model,
                max_output_tokens=args.max_output_tokens,
            )

            run = translator.translate(
                source,
                commentaries,
            )

        except BudgetError as exc:
            print(
                "⛔ Budget épuisé : "
                f"{exc}"
            )
            print(
                "Le traitement est arrêté avant tout "
                "nouvel appel API."
            )
            return 1

        except (
            OpenAIEngineError,
            ValueError,
            TypeError,
        ) as exc:
            failed_cost = budget.record_error(
                selected_model,
                exc,
            )

            failures.append({
                "daf": daf,
                "segment": number,
                "model": selected_model,
                "error": str(exc),
                "cost_eur": failed_cost,
            })

            run_cost += failed_cost

            print(
                "❌ Segment refusé : "
                f"{exc}"
            )

            if failed_cost:
                print(
                    "💶 Coût de l’appel échoué : "
                    f"{failed_cost:.6f} €"
                )

            print(
                "⏭️ Passage automatique au segment suivant."
            )
            continue

        metadata = budget_metadata(
            model=selected_model,
            input_tokens=run.api.input_tokens,
            output_tokens=run.api.output_tokens,
        )

        segment_cost = budget.record_result(
            metadata
        )

        cost_payload = {
            "segment_eur": segment_cost,
            "phase_spent_eur": budget.spent_eur,
            "phase_remaining_eur": budget.remaining_eur,
        }

        sample_for_review = (
            number == 1
            or (number - 1) % 20 == 0
        )

        quality_report = analyse_translation(
            ref=(
                f"{source.masechet.title()} "
                f"{source.daf}:{source.segment_number}"
            ),
            hebrew=source.hebrew,
            english=source.english,
            french=run.translation_fr,
            commentaries=run.commentaries,
            confidence=run.confidence,
            model=selected_model,
            sample_for_review=sample_for_review,
        )

        apply_aligned_translation(
            segment,
            source,
            run,
            model=selected_model,
            cost=cost_payload,
        )

        segment["fr_editorial"]["quality"] = {
            "status": (
                "flagged"
                if quality_report.flagged
                else "translated"
            ),
            "flagged": quality_report.flagged,
            "reasons": quality_report.reasons,
            "sample_for_review": sample_for_review,
        }

        save_document_atomic(
            corpus_path,
            document,
        )

        review_queue.update(
            quality_report
        )

        saved += 1
        run_cost += segment_cost
        run_tokens += run.api.total_tokens

        print("✅ Traduction alignée sauvegardée.")
        print(
            "📝 Traduction :",
            run.translation_fr,
        )

        for key in ("rachi", "tossefot"):
            entry = run.commentaries.get(key)

            if isinstance(entry, dict):
                print(
                    f"📖 {key.capitalize()} : "
                    f"{entry.get('summary', '')}"
                )

        if quality_report.flagged:
            print("⚠️ Segment ajouté à la file de révision :")

            for reason in quality_report.reasons:
                print(f"   - {reason}")
        else:
            print("✅ Contrôle local : aucune anomalie détectée.")

        print(
            "📊 Tokens : "
            f"{run.api.total_tokens}"
        )
        print(
            "💶 Coût estimé : "
            f"{segment_cost:.6f} €"
        )
        print(
            "💶 Budget restant : "
            f"{budget.remaining_eur:.6f} €"
        )

    print("\n" + "=" * 60)
    print("✅ Exécution terminée")
    print(f"Segments sauvegardés : {saved}")
    print(f"Segments ignorés : {skipped}")
    print(f"Segments refusés : {len(failures)}")
    print(f"Tokens de cette exécution : {run_tokens}")
    print(
        "Coût de cette exécution : "
        f"{run_cost:.6f} €"
    )
    print(
        "Budget restant : "
        f"{budget.remaining_eur:.6f} €"
    )

    if failures:
        print("\n⚠️ Segments à reprendre manuellement :")

        for failure in failures:
            print(
                "  - "
                f"{failure['daf']}:{failure['segment']} — "
                f"{failure['error']}"
            )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
