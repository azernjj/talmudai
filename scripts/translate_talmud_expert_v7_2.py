#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_FROM_SCRIPT = SCRIPT_DIR.parent

if str(ROOT_FROM_SCRIPT) not in sys.path:
    sys.path.insert(0, str(ROOT_FROM_SCRIPT))

from engine_v7_2.budget import BudgetError, BudgetGuard
from engine_v7_2.checkpoint import CheckpointStore
from engine_v7_2.commentary_loader import CommentaryLibrary
from engine_v7_2.config import EnginePaths
from engine_v7_2.context_builder import ContextBuilder
from engine_v7_2.corpus_writer import (
    apply_translation_to_segment,
    save_document,
)
from engine_v7_2.diagnostics import format_summary
from engine_v7_2.loader import extract_hebrew_text, load_document
from engine_v7_2.naming import canonical_name
from engine_v7_2.openai_client import (
    OpenAIEngineError,
    ResponsesJsonClient,
)
from engine_v7_2.pipeline import EditorialPipeline
from engine_v7_2.project_index import ProjectScanner
from engine_v7_2.prompts import load_charter
from engine_v7_2.reporting import write_run_report
from engine_v7_2.reviewer import Reviewer
from engine_v7_2.terminology import TerminologyStore
from engine_v7_2.translator import Translator


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="TALMUD AI V7.2 — moteur éditorial structuré"
    )
    p.add_argument(
        "--project-root",
        default=".",
        help="Racine du projet TALMUD AI.",
    )
    p.add_argument(
        "--scan",
        action="store_true",
        help="Analyse le projet et quitte si aucun fichier n'est indiqué.",
    )
    p.add_argument(
        "--file",
        help="Fichier JSON du traité à traduire.",
    )
    p.add_argument(
        "--only-daf",
        help="Daf à traiter, par exemple 2a.",
    )
    p.add_argument(
        "--start-segment",
        type=int,
        default=1,
        help="Numéro humain du premier segment, à partir de 1.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Nombre maximal de segments consécutifs à traiter.",
    )
    p.add_argument(
        "--model-translator",
        default="gpt-5-nano",
    )
    p.add_argument(
        "--model-reviewer",
        default="gpt-5-nano",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Contrôle le chargement sans appel API ni écriture.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Remplace les traductions françaises existantes.",
    )
    return p


def register_commentaries(
    library: CommentaryLibrary,
    index: Any,
    key: str,
) -> None:
    record = index.tractates.get(key)

    if not record:
        return

    for name, source in record.commentaries.items():
        if source.valid:
            library.register(
                record.display_name,
                name,
                source.path,
            )


def _resolve_file_path(
    raw_path: str,
    project_root: Path,
) -> Path:
    file_path = Path(raw_path)

    if not file_path.is_absolute():
        file_path = project_root / file_path

    file_path = file_path.resolve()

    if not file_path.exists():
        raise SystemExit(
            f"Fichier introuvable : {file_path}"
        )

    if not file_path.is_file():
        raise SystemExit(
            f"Le chemin n'est pas un fichier : {file_path}"
        )

    return file_path


def _build_report_payload(
    *,
    masechet: str,
    daf: str,
    segment_number: int,
    result: Any,
) -> dict[str, Any]:
    return {
        "masechet": masechet,
        "daf": daf,
        "segment": segment_number,
        "final": result.final,
        "validation": {
            "valid": result.validation.valid,
            "errors": list(result.validation.errors),
            "warnings": list(result.validation.warnings),
        },
        "metadata": result.metadata,
    }


def main() -> int:
    args = parser().parse_args()

    if args.start_segment < 1:
        raise SystemExit(
            "--start-segment doit être supérieur ou égal à 1."
        )

    if args.limit < 1:
        raise SystemExit(
            "--limit doit être supérieur ou égal à 1."
        )

    paths = EnginePaths.from_project_root(
        args.project_root
    )
    paths.ensure_runtime_directories()

    try:
        budget = BudgetGuard(paths.project_root)
    except BudgetError as exc:
        raise SystemExit(
            f"Erreur budgétaire : {exc}"
        ) from exc

    print("\n💶 Budget de la phase légère")
    print(
        "  Plafond :",
        f"{budget.state['limit_eur']:.2f} €",
    )
    print(
        "  Dépensé :",
        f"{budget.spent_eur:.6f} €",
    )
    print(
        "  Restant :",
        f"{budget.remaining_eur:.6f} €",
    )
    print("  Fichier :", budget.path)

    scanner = ProjectScanner(paths)
    index = scanner.scan()
    scanner.save(index)

    print(
        format_summary(
            index,
            len(scanner.ignored_files),
        )
    )

    if not args.file:
        return 0

    if not args.only_daf:
        raise SystemExit(
            "--only-daf est obligatoire avec --file."
        )

    file_path = _resolve_file_path(
        args.file,
        paths.project_root,
    )
    document = load_document(file_path)

    masechet = str(
        document.get("masechet")
        or document.get("tractate")
        or file_path.stem
    )
    key = canonical_name(masechet)

    library = CommentaryLibrary()
    register_commentaries(
        library,
        index,
        key,
    )
    builder = ContextBuilder(library)

    first_target = builder.build_segment_target(
        document=document,
        masechet=masechet,
        daf=args.only_daf,
        segment_number=args.start_segment,
    )

    print(
        f"\n🔎 {masechet} "
        f"{args.only_daf}:{args.start_segment}"
    )
    print(
        "📚 Commentaires disponibles :",
        sorted(first_target.commentary_texts) or "aucun",
    )
    print(
        "📝 Texte central :",
        len(extract_hebrew_text(first_target.segment)),
        "caractères",
    )

    if args.dry_run:
        print(
            "✅ Dry-run : aucun appel API, "
            "aucune modification."
        )
        return 0

    terminology = TerminologyStore(
        paths.lexicon_path,
        paths.translation_memory_path,
    )
    terminology.load()

    charter = load_charter(paths.charter_path)
    client = ResponsesJsonClient()

    translator = Translator(
        client,
        args.model_translator,
        charter,
        terminology.get_prompt_rules(),
    )
    reviewer = Reviewer(
        client,
        args.model_reviewer,
        charter,
        terminology.get_prompt_rules(),
    )
    pipeline = EditorialPipeline(
        translator,
        reviewer,
    )
    checkpoint = CheckpointStore(
        paths.checkpoints_dir
    )

    processed = 0
    skipped = 0
    total_tokens = 0
    run_cost_eur = 0.0
    last_report_path: Path | None = None
    last_checkpoint_path: Path | None = None

    for offset in range(args.limit):
        segment_number = args.start_segment + offset

        try:
            target = builder.build_segment_target(
                document=document,
                masechet=masechet,
                daf=args.only_daf,
                segment_number=segment_number,
            )
        except (IndexError, KeyError, ValueError) as exc:
            print(
                f"\n⏹️ Arrêt à {args.only_daf}:"
                f"{segment_number} — {exc}"
            )
            break

        print(
            f"\n🔎 Traitement de "
            f"{masechet} {args.only_daf}:"
            f"{segment_number}"
        )

        existing = target.segment.get("fr")

        if (
            isinstance(existing, str)
            and existing.strip()
            and not args.force
        ):
            skipped += 1
            print(
                "⏭️ Traduction déjà présente : "
                "segment ignoré."
            )
            continue

        try:
            budget.ensure_call_allowed()
        except BudgetError as exc:
            print(f"\n⛔ Arrêt budgétaire : {exc}")
            break

        try:
            result = pipeline.run(target)
        except OpenAIEngineError as exc:
            failed_cost = budget.record_error(
                args.model_reviewer,
                exc,
            )
            print(f"\n❌ Appel API interrompu : {exc}")
            print(
                "💶 Coût comptabilisé :",
                f"{failed_cost:.6f} €",
            )
            print(
                "💶 Budget restant :",
                f"{budget.remaining_eur:.6f} €",
            )
            return 3

        segment_cost = budget.record_result(
            result.metadata
        )
        run_cost_eur += segment_cost

        result.metadata["cost"] = {
            "segment_eur": segment_cost,
            "run_eur": run_cost_eur,
            "spent_eur": budget.spent_eur,
            "remaining_eur": budget.remaining_eur,
            "limit_eur": budget.state["limit_eur"],
        }

        report_payload = _build_report_payload(
            masechet=masechet,
            daf=args.only_daf,
            segment_number=segment_number,
            result=result,
        )
        report_path = write_run_report(
            paths.reports_dir,
            report_payload,
        )
        last_report_path = Path(report_path)

        if result.validation.warnings:
            print("\n⚠️ Avertissements :")
            for warning in result.validation.warnings:
                print("  -", warning)

        if not result.validation.valid:
            print("\n❌ Validation refusée :")
            for error in result.validation.errors:
                print("  -", error)
            print("📄 Rapport :", report_path)
            print(
                "⛔ Le corpus n'a pas été modifié "
                "pour ce segment."
            )
            return 2

        apply_translation_to_segment(
            document=document,
            daf=args.only_daf,
            segment_index=target.segment_index,
            final=result.final,
            metadata=result.metadata,
        )
        save_document(
            file_path,
            document,
        )

        checkpoint_path = checkpoint.save(
            masechet,
            {
                "engine_version": "7.2",
                "file": str(file_path),
                "daf": args.only_daf,
                "segment": segment_number,
                "segment_index": target.segment_index,
                "report": str(report_path),
                "tokens": result.metadata["tokens"],
                "cost": result.metadata.get("cost", {}),
                "validation": result.metadata.get(
                    "validation",
                    {},
                ),
            },
        )
        last_checkpoint_path = Path(checkpoint_path)

        segment_tokens = int(
            result.metadata
            .get("tokens", {})
            .get("total", 0)
            or 0
        )
        total_tokens += segment_tokens
        processed += 1

        print("✅ Traduction validée et sauvegardée.")
        print("📊 Tokens du segment :", segment_tokens)
        print(
            "💶 Coût estimé du segment :",
            f"{segment_cost:.6f} €",
        )
        print(
            "💶 Dépensé sur la phase légère :",
            f"{budget.spent_eur:.6f} €",
        )
        print(
            "💶 Budget restant :",
            f"{budget.remaining_eur:.6f} €",
        )
        print("📄 Rapport :", report_path)
        print("📍 Checkpoint :", checkpoint_path)

    print("\n" + "=" * 60)
    print("✅ Exécution V7.2 terminée")
    print("Segments sauvegardés :", processed)
    print("Segments ignorés :", skipped)
    print("Tokens totaux :", total_tokens)
    print(
        "Coût estimé de cette exécution :",
        f"{run_cost_eur:.6f} €",
    )
    print(
        "Coût cumulé de la phase légère :",
        f"{budget.spent_eur:.6f} €",
    )
    print(
        "Budget restant :",
        f"{budget.remaining_eur:.6f} €",
    )

    if last_report_path:
        print("Dernier rapport :", last_report_path)

    if last_checkpoint_path:
        print(
            "Dernier checkpoint :",
            last_checkpoint_path,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
