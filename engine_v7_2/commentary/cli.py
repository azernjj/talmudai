from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from .checkpoint import (
    CommentaryCheckpointError,
    CommentaryCheckpointManager,
)
from .downloader import (
    CommentaryDownloadError,
    CommentaryDownloader,
    DownloadOptions,
)
from .index import CommentaryIndexer
from .loader import CommentaryLoader
from .registry import (
    get_commentary,
    list_commentaries,
    normalize_commentary_key,
)
from .validator import CommentaryValidator


DEFAULT_DATA_ROOT = Path(
    "public/data/commentaries"
)

DEFAULT_CHECKPOINT_ROOT = Path(
    "checkpoints/commentaries"
)


class CommentaryCLIError(RuntimeError):
    """
    Erreur d’utilisation de l’interface Commentary V7.2.
    """


def print_heading(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_key_value(
    label: str,
    value: Any,
    *,
    width: int = 20,
) -> None:
    print(f"{label:<{width}}: {value}")


def print_json(payload: Any) -> None:
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )


def format_seconds(value: float) -> str:
    seconds = max(0.0, float(value))

    if seconds < 60:
        return f"{seconds:.2f} s"

    minutes, remaining_seconds = divmod(
        seconds,
        60,
    )

    if minutes < 60:
        return (
            f"{int(minutes)} min "
            f"{remaining_seconds:.1f} s"
        )

    hours, remaining_minutes = divmod(
        int(minutes),
        60,
    )

    return (
        f"{hours} h "
        f"{remaining_minutes} min "
        f"{remaining_seconds:.1f} s"
    )


def normalize_path(value: str | Path) -> Path:
    return Path(value).expanduser()


def iter_commentary_files(
    root: str | Path,
) -> list[Path]:
    root_path = normalize_path(root)

    if not root_path.exists():
        return []

    return sorted(
        path
        for path in root_path.rglob("*.json")
        if path.name != "index.json"
    )


def load_document_safely(
    loader: CommentaryLoader,
    path: Path,
):
    try:
        document = loader.load_file(path)
        return document, None
    except Exception as exc:
        return None, str(exc)


def command_registry(
    args: argparse.Namespace,
) -> int:
    print_heading(
        "Registre des commentaires — TALMUD AI V7.2"
    )

    definitions = list_commentaries()

    if not definitions:
        print("Aucun commentaire enregistré.")
        return 0

    for definition in definitions:
        key = getattr(
            definition,
            "key",
            "",
        )

        display_name = getattr(
            definition,
            "display_name",
            key,
        )

        priority = getattr(
            definition,
            "priority",
            "",
        )

        enabled = getattr(
            definition,
            "enabled",
            True,
        )

        aliases = getattr(
            definition,
            "aliases",
            (),
        )

        print_key_value(
            "Clé",
            key,
        )
        print_key_value(
            "Nom",
            display_name,
        )
        print_key_value(
            "Priorité",
            priority,
        )
        print_key_value(
            "Actif",
            "oui" if enabled else "non",
        )

        if aliases:
            print_key_value(
                "Alias",
                ", ".join(
                    str(alias)
                    for alias in aliases
                ),
            )

        print("-" * 72)

    print_key_value(
        "Total",
        len(definitions),
    )

    return 0


def command_validate(
    args: argparse.Namespace,
) -> int:
    root = normalize_path(args.root)

    loader = CommentaryLoader(
        root=root,
        validate=False,
        allow_unknown_commentary=(
            args.allow_unknown
        ),
        include_empty_comments=True,
        strict_validation=False,
    )

    validator = CommentaryValidator(
        allow_unknown_commentary=(
            args.allow_unknown
        )
    )

    if args.path:
        requested_path = normalize_path(
            args.path
        )

        if requested_path.is_dir():
            files = sorted(
                path
                for path in requested_path.rglob(
                    "*.json"
                )
                if path.name != "index.json"
            )
        else:
            files = [requested_path]
    else:
        files = iter_commentary_files(root)

    if not files:
        print(
            "Aucun fichier de commentaire trouvé."
        )
        return 1

    print_heading(
        "Validation des commentaires — TALMUD AI V7.2"
    )

    valid_count = 0
    invalid_count = 0
    warning_count = 0
    total_dapim = 0
    total_comments = 0

    for path in files:
        try:
            document = loader.load_file(path)

            report = validator.validate_document(
                document,
                source_path=path,
            )

            errors = list(
                getattr(
                    report,
                    "errors",
                    [],
                )
            )

            warnings = list(
                getattr(
                    report,
                    "warnings",
                    [],
                )
            )

            is_valid = bool(
                getattr(
                    report,
                    "is_valid",
                    not errors,
                )
            )

            if is_valid:
                valid_count += 1
                status = "✅ VALIDE"
            else:
                invalid_count += 1
                status = "❌ INVALIDE"

            warning_count += len(warnings)
            total_dapim += document.daf_count()
            total_comments += (
                document.comment_count()
            )

            print()
            print(f"{status} — {path}")
            print_key_value(
                "Commentaire",
                document.commentary,
            )
            print_key_value(
                "Traité",
                document.masechet,
            )
            print_key_value(
                "Dapim",
                document.daf_count(),
            )
            print_key_value(
                "Commentaires",
                document.comment_count(),
            )

            if errors:
                print("  Erreurs :")

                for issue in errors:
                    message = getattr(
                        issue,
                        "message",
                        str(issue),
                    )
                    location = getattr(
                        issue,
                        "location",
                        "",
                    )

                    if location:
                        print(
                            f"    - {location}: "
                            f"{message}"
                        )
                    else:
                        print(
                            f"    - {message}"
                        )

            if warnings and args.show_warnings:
                print("  Avertissements :")

                for issue in warnings:
                    message = getattr(
                        issue,
                        "message",
                        str(issue),
                    )
                    location = getattr(
                        issue,
                        "location",
                        "",
                    )

                    if location:
                        print(
                            f"    - {location}: "
                            f"{message}"
                        )
                    else:
                        print(
                            f"    - {message}"
                        )

        except Exception as exc:
            invalid_count += 1

            print()
            print(f"❌ ERREUR — {path}")
            print(f"  {exc}")

            if args.stop_on_error:
                break

    print_heading("Résumé")

    print_key_value(
        "Fichiers analysés",
        valid_count + invalid_count,
    )
    print_key_value(
        "Fichiers valides",
        valid_count,
    )
    print_key_value(
        "Fichiers invalides",
        invalid_count,
    )
    print_key_value(
        "Avertissements",
        warning_count,
    )
    print_key_value(
        "Dapim",
        total_dapim,
    )
    print_key_value(
        "Commentaires",
        total_comments,
    )

    return 0 if invalid_count == 0 else 2


def command_stats(
    args: argparse.Namespace,
) -> int:
    root = normalize_path(args.root)

    loader = CommentaryLoader(
        root=root,
        validate=not args.no_validate,
        allow_unknown_commentary=(
            args.allow_unknown
        ),
        include_empty_comments=True,
        strict_validation=False,
    )

    files = iter_commentary_files(root)

    if not files:
        print(
            f"Aucun commentaire trouvé dans {root}."
        )
        return 1

    commentary_stats: dict[
        str,
        dict[str, Any],
    ] = {}

    failures: dict[str, str] = {}

    total_dapim = 0
    total_comments = 0

    for path in files:
        document, error = load_document_safely(
            loader,
            path,
        )

        if error:
            failures[str(path)] = error
            continue

        commentary_key = (
            document.commentary_key
            or normalize_commentary_key(
                document.commentary
            )
        )

        entry = commentary_stats.setdefault(
            commentary_key,
            {
                "commentary": (
                    document.commentary
                ),
                "files": 0,
                "masechtot": set(),
                "dapim": 0,
                "comments": 0,
            },
        )

        entry["files"] += 1
        entry["masechtot"].add(
            document.masechet
        )
        entry["dapim"] += document.daf_count()
        entry["comments"] += (
            document.comment_count()
        )

        total_dapim += document.daf_count()
        total_comments += (
            document.comment_count()
        )

    if args.json:
        output: dict[str, Any] = {
            "root": str(root),
            "files": len(files),
            "loaded_files": (
                len(files) - len(failures)
            ),
            "failed_files": len(failures),
            "dapim": total_dapim,
            "comments": total_comments,
            "commentaries": {},
            "failures": failures,
        }

        for key, entry in sorted(
            commentary_stats.items()
        ):
            output["commentaries"][key] = {
                "commentary": (
                    entry["commentary"]
                ),
                "files": entry["files"],
                "masechtot": sorted(
                    entry["masechtot"]
                ),
                "masechtot_count": len(
                    entry["masechtot"]
                ),
                "dapim": entry["dapim"],
                "comments": entry["comments"],
            }

        print_json(output)
        return 0 if not failures else 2

    print_heading(
        "Statistiques des commentaires — TALMUD AI V7.2"
    )

    for key, entry in sorted(
        commentary_stats.items(),
        key=lambda pair: (
            -pair[1]["comments"],
            pair[0],
        ),
    ):
        print()
        print(
            f"{entry['commentary']} "
            f"({key})"
        )
        print("-" * 72)
        print_key_value(
            "Fichiers",
            entry["files"],
        )
        print_key_value(
            "Traités",
            len(entry["masechtot"]),
        )
        print_key_value(
            "Dapim",
            entry["dapim"],
        )
        print_key_value(
            "Commentaires",
            entry["comments"],
        )

        if args.show_masechtot:
            print_key_value(
                "Liste",
                ", ".join(
                    sorted(entry["masechtot"])
                ),
            )

    print_heading("Total général")

    print_key_value(
        "Racine",
        root,
    )
    print_key_value(
        "Fichiers",
        len(files),
    )
    print_key_value(
        "Fichiers chargés",
        len(files) - len(failures),
    )
    print_key_value(
        "Échecs",
        len(failures),
    )
    print_key_value(
        "Dapim",
        total_dapim,
    )
    print_key_value(
        "Commentaires",
        total_comments,
    )

    if failures:
        print()
        print("Fichiers en erreur :")

        for path, error in failures.items():
            print(f"  - {path}: {error}")

    return 0 if not failures else 2


def command_index(
    args: argparse.Namespace,
) -> int:
    root = normalize_path(args.root)

    print_heading(
        "Construction de l’index — TALMUD AI V7.2"
    )

    started_at = time.monotonic()

    indexer = CommentaryIndexer(
        root_directory=root
    )

    index = indexer.build()

    if args.output:
        output_path = normalize_path(
            args.output
        )
        saved_path = indexer.save(
            index,
            path=output_path,
        )
    else:
        saved_path = indexer.save(index)

    elapsed = time.monotonic() - started_at

    print_key_value(
        "Index écrit",
        saved_path,
    )

    if isinstance(index, dict):
        print_key_value(
            "Entrées",
            len(index),
        )

    print_key_value(
        "Durée",
        format_seconds(elapsed),
    )

    return 0


def build_download_options(
    args: argparse.Namespace,
) -> DownloadOptions:
    return DownloadOptions(
        timeout=args.timeout,
        retries=args.retries,
        retry_delay=args.retry_delay,
        retry_backoff=args.retry_backoff,
        request_delay=args.request_delay,
        jitter=args.jitter,
        include_translation=(
            not args.no_translation
        ),
        fill_missing_segments=(
            not args.no_fill_missing
        ),
    )


def build_downloader(
    args: argparse.Namespace,
) -> CommentaryDownloader:
    return CommentaryDownloader(
        data_root=normalize_path(args.root),
        options=build_download_options(args),
    )


def command_download_daf(
    args: argparse.Namespace,
) -> int:
    downloader = build_downloader(args)

    print_heading(
        "Téléchargement d’un daf — TALMUD AI V7.2"
    )

    try:
        result = downloader.download_daf(
            commentary=args.commentary,
            masechet=args.masechet,
            daf=args.daf,
            sefaria_title=args.sefaria_title,
        )
    except Exception as exc:
        print(f"❌ Échec : {exc}")
        return 2

    print_key_value(
        "Commentaire",
        result.commentary,
    )
    print_key_value(
        "Clé",
        result.commentary_key,
    )
    print_key_value(
        "Traité",
        result.masechet,
    )
    print_key_value(
        "Daf",
        result.daf,
    )
    print_key_value(
        "Référence",
        result.sefaria_ref,
    )
    print_key_value(
        "Commentaires",
        result.comment_count,
    )
    print_key_value(
        "Version hébraïque",
        result.source_version_title or "—",
    )
    print_key_value(
        "Version anglaise",
        (
            result.translation_version_title
            or "—"
        ),
    )
    print_key_value(
        "Requêtes",
        result.request_count,
    )

    if result.warnings:
        print()
        print("Avertissements :")

        for warning in result.warnings:
            print(f"  - {warning}")

    if args.show_text:
        limit = (
            len(result.comments)
            if args.limit is None
            else max(0, args.limit)
        )

        for index, comment in enumerate(
            result.comments[:limit],
            start=1,
        ):
            print()
            print(
                f"Commentaire {index}"
            )
            print("-" * 72)
            print_key_value(
                "Référence",
                comment.ref,
            )
            print_key_value(
                "Dibour hamathil",
                (
                    comment.dibur_hamatchil
                    or "—"
                ),
            )
            print("Hébreu :")
            print(comment.he or "—")

            if comment.en:
                print()
                print("Anglais :")
                print(comment.en)

            if comment.fr:
                print()
                print("Français :")
                print(comment.fr)

    return 0


def command_download(
    args: argparse.Namespace,
) -> int:
    downloader = build_downloader(args)

    destination = (
        normalize_path(args.destination)
        if args.destination
        else None
    )

    print_heading(
        "Téléchargement d’un traité — TALMUD AI V7.2"
    )

    print_key_value(
        "Commentaire",
        args.commentary,
    )
    print_key_value(
        "Traité",
        args.masechet,
    )

    if args.daf:
        print_key_value(
            "Dapim",
            ", ".join(args.daf),
        )
    else:
        print_key_value(
            "Début",
            args.start,
        )
        print_key_value(
            "Fin",
            args.end,
        )

    try:
        result = downloader.download_masechet(
            commentary=args.commentary,
            masechet=args.masechet,
            dapim=args.daf,
            start_daf=args.start,
            end_daf=args.end,
            sefaria_title=args.sefaria_title,
            destination=destination,
            force=args.force,
            keep_empty_dapim=args.keep_empty,
            stop_on_error=args.stop_on_error,
            backup=not args.no_backup,
            rebuild_index=args.rebuild_index,
        )
    except Exception as exc:
        print()
        print(f"❌ Téléchargement impossible : {exc}")
        return 2

    print_heading("Résultat")

    stats = result.statistics()

    print_key_value(
        "Succès",
        "oui" if result.success else "non",
    )
    print_key_value(
        "Destination",
        result.destination,
    )
    print_key_value(
        "Dapim téléchargés",
        len(result.downloaded_dapim),
    )
    print_key_value(
        "Dapim ignorés",
        len(result.skipped_dapim),
    )
    print_key_value(
        "Dapim vides",
        len(result.empty_dapim),
    )
    print_key_value(
        "Dapim en échec",
        len(result.failed_dapim),
    )
    print_key_value(
        "Dapim dans fichier",
        stats["dapim_in_document"],
    )
    print_key_value(
        "Commentaires",
        stats["comments_in_document"],
    )
    print_key_value(
        "Requêtes",
        result.request_count,
    )
    print_key_value(
        "Durée",
        format_seconds(
            result.elapsed_seconds
        ),
    )
    print_key_value(
        "Index reconstruit",
        (
            "oui"
            if result.index_rebuilt
            else "non"
        ),
    )

    if result.downloaded_dapim:
        print()
        print(
            "Téléchargés : "
            + ", ".join(
                result.downloaded_dapim
            )
        )

    if result.skipped_dapim:
        print()
        print(
            "Déjà présents : "
            + ", ".join(
                result.skipped_dapim
            )
        )

    if result.empty_dapim:
        print()
        print(
            "Sans commentaire : "
            + ", ".join(
                result.empty_dapim
            )
        )

    if result.failed_dapim:
        print()
        print("Échecs :")

        for daf, error in (
            result.failed_dapim.items()
        ):
            print(f"  - {daf}: {error}")

    return 0 if result.success else 2


def command_import_file(
    args: argparse.Namespace,
) -> int:
    downloader = build_downloader(args)

    source = normalize_path(args.source)

    destination = (
        normalize_path(args.destination)
        if args.destination
        else None
    )

    print_heading(
        "Import d’un commentaire local — TALMUD AI V7.2"
    )

    try:
        document = downloader.import_local_file(
            source,
            destination=destination,
            backup=not args.no_backup,
            rebuild_index=args.rebuild_index,
        )
    except Exception as exc:
        print(f"❌ Import impossible : {exc}")
        return 2

    print_key_value(
        "Source",
        source,
    )
    print_key_value(
        "Commentaire",
        document.commentary,
    )
    print_key_value(
        "Clé",
        document.commentary_key,
    )
    print_key_value(
        "Traité",
        document.masechet,
    )
    print_key_value(
        "Dapim",
        document.daf_count(),
    )
    print_key_value(
        "Commentaires",
        document.comment_count(),
    )

    print()
    print("✅ Import terminé.")

    return 0


def command_import_directory(
    args: argparse.Namespace,
) -> int:
    downloader = build_downloader(args)

    source = normalize_path(args.source)

    print_heading(
        "Import d’un dossier — TALMUD AI V7.2"
    )

    try:
        documents = (
            downloader.import_local_directory(
                source,
                pattern=args.pattern,
                rebuild_index=(
                    args.rebuild_index
                ),
            )
        )
    except Exception as exc:
        print(f"❌ Import impossible : {exc}")
        return 2

    total_dapim = sum(
        document.daf_count()
        for document in documents
    )

    total_comments = sum(
        document.comment_count()
        for document in documents
    )

    print_key_value(
        "Dossier",
        source,
    )
    print_key_value(
        "Documents",
        len(documents),
    )
    print_key_value(
        "Dapim",
        total_dapim,
    )
    print_key_value(
        "Commentaires",
        total_comments,
    )

    print()
    print("✅ Import terminé.")

    return 0


def command_checkpoint(
    args: argparse.Namespace,
) -> int:
    manager = CommentaryCheckpointManager(
        root_directory=normalize_path(
            args.checkpoint_root
        )
    )

    try:
        checkpoint = manager.load(
            args.commentary,
            args.masechet,
        )
    except CommentaryCheckpointError as exc:
        print(f"❌ {exc}")
        return 2

    stats = checkpoint.statistics()

    if args.json:
        print_json(
            {
                "commentary_key": (
                    checkpoint.commentary_key
                ),
                "masechet": checkpoint.masechet,
                "source_file": (
                    checkpoint.source_file
                ),
                "destination_file": (
                    checkpoint.destination_file
                ),
                "model": checkpoint.model,
                "created_at": (
                    checkpoint.created_at
                ),
                "updated_at": (
                    checkpoint.updated_at
                ),
                "completion_rate": (
                    checkpoint.completion_rate()
                ),
                "complete": (
                    checkpoint.is_complete()
                ),
                "statistics": stats,
            }
        )
        return 0

    print_heading(
        "Checkpoint de traduction — TALMUD AI V7.2"
    )

    print_key_value(
        "Commentaire",
        checkpoint.commentary_key,
    )
    print_key_value(
        "Traité",
        checkpoint.masechet,
    )
    print_key_value(
        "Modèle",
        checkpoint.model or "—",
    )
    print_key_value(
        "Source",
        checkpoint.source_file or "—",
    )
    print_key_value(
        "Destination",
        checkpoint.destination_file or "—",
    )
    print_key_value(
        "Créé",
        checkpoint.created_at,
    )
    print_key_value(
        "Mis à jour",
        checkpoint.updated_at,
    )

    print()
    print_key_value(
        "Total",
        stats["total"],
    )
    print_key_value(
        "En attente",
        stats["pending"],
    )
    print_key_value(
        "En traitement",
        stats["processing"],
    )
    print_key_value(
        "Terminés",
        stats["completed"],
    )
    print_key_value(
        "Échecs",
        stats["failed"],
    )
    print_key_value(
        "Ignorés",
        stats["skipped"],
    )
    print_key_value(
        "Tentatives",
        stats["attempts"],
    )
    print_key_value(
        "Progression",
        f"{checkpoint.completion_rate():.2f} %",
    )
    print_key_value(
        "Complet",
        (
            "oui"
            if checkpoint.is_complete()
            else "non"
        ),
    )

    if args.show_pending:
        pending = checkpoint.pending_items(
            retry_failed=True,
            retry_processing=True,
        )

        print()
        print(
            f"Éléments à reprendre : "
            f"{len(pending)}"
        )

        limit = (
            len(pending)
            if args.limit is None
            else max(0, args.limit)
        )

        for item in pending[:limit]:
            print(
                f"  - {item.daf}:"
                f"{item.comment_index} "
                f"statut={item.status} "
                f"tentatives={item.attempts}"
            )

            if item.error:
                print(
                    f"      erreur={item.error}"
                )

    return 0


def command_checkpoint_reset_processing(
    args: argparse.Namespace,
) -> int:
    manager = CommentaryCheckpointManager(
        root_directory=normalize_path(
            args.checkpoint_root
        )
    )

    try:
        checkpoint = manager.load(
            args.commentary,
            args.masechet,
        )

        count = manager.reset_processing_items(
            checkpoint
        )

        if count:
            manager.save(checkpoint)

    except CommentaryCheckpointError as exc:
        print(f"❌ {exc}")
        return 2

    print_key_value(
        "Entrées réinitialisées",
        count,
    )

    return 0


def command_checkpoint_delete(
    args: argparse.Namespace,
) -> int:
    manager = CommentaryCheckpointManager(
        root_directory=normalize_path(
            args.checkpoint_root
        )
    )

    if not args.yes:
        print(
            "Suppression annulée : ajoute --yes "
            "pour confirmer."
        )
        return 1

    try:
        deleted = manager.delete(
            args.commentary,
            args.masechet,
            missing_ok=False,
        )
    except CommentaryCheckpointError as exc:
        print(f"❌ {exc}")
        return 2

    print(
        "✅ Checkpoint supprimé."
        if deleted
        else "Checkpoint absent."
    )

    return 0


def add_root_argument(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--root",
        default=str(DEFAULT_DATA_ROOT),
        help=(
            "Racine des commentaires "
            f"(défaut : {DEFAULT_DATA_ROOT})."
        ),
    )


def add_network_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=45.0,
        help="Délai maximal d’une requête HTTP.",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="Nombre de nouvelles tentatives.",
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help=(
            "Attente initiale avant une nouvelle "
            "tentative."
        ),
    )

    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=2.0,
        help=(
            "Multiplicateur du délai entre les "
            "tentatives."
        ),
    )

    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.35,
        help=(
            "Attente minimale entre les requêtes."
        ),
    )

    parser.add_argument(
        "--jitter",
        type=float,
        default=0.15,
        help=(
            "Délai aléatoire ajouté aux attentes."
        ),
    )

    parser.add_argument(
        "--no-translation",
        action="store_true",
        help=(
            "Ne pas demander de traduction anglaise."
        ),
    )

    parser.add_argument(
        "--no-fill-missing",
        action="store_true",
        help=(
            "Désactiver le remplissage des segments "
            "manquants par Sefaria."
        ),
    )


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=(
            "python3 -m "
            "engine_v7_2.commentary.cli"
        ),
        description=(
            "Interface de gestion des commentaires "
            "de TALMUD AI V7.2."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version="TALMUD AI Commentary CLI V7.2",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    registry_parser = subparsers.add_parser(
        "registry",
        help=(
            "Afficher le registre des commentaires."
        ),
    )

    registry_parser.set_defaults(
        handler=command_registry
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help=(
            "Valider un fichier ou tous les "
            "commentaires."
        ),
    )

    add_root_argument(validate_parser)

    validate_parser.add_argument(
        "path",
        nargs="?",
        help=(
            "Fichier ou dossier à valider. "
            "Sans valeur, utilise --root."
        ),
    )

    validate_parser.add_argument(
        "--allow-unknown",
        action="store_true",
        help=(
            "Accepter les commentaires absents "
            "du registre."
        ),
    )

    validate_parser.add_argument(
        "--show-warnings",
        action="store_true",
        help=(
            "Afficher le détail des avertissements."
        ),
    )

    validate_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help=(
            "Arrêter dès le premier fichier invalide."
        ),
    )

    validate_parser.set_defaults(
        handler=command_validate
    )

    stats_parser = subparsers.add_parser(
        "stats",
        help=(
            "Afficher les statistiques globales."
        ),
    )

    add_root_argument(stats_parser)

    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Afficher les résultats en JSON.",
    )

    stats_parser.add_argument(
        "--show-masechtot",
        action="store_true",
        help=(
            "Afficher la liste des traités."
        ),
    )

    stats_parser.add_argument(
        "--allow-unknown",
        action="store_true",
        help=(
            "Accepter les commentaires absents "
            "du registre."
        ),
    )

    stats_parser.add_argument(
        "--no-validate",
        action="store_true",
        help=(
            "Ne pas valider pendant le chargement."
        ),
    )

    stats_parser.set_defaults(
        handler=command_stats
    )

    index_parser = subparsers.add_parser(
        "index",
        help=(
            "Reconstruire l’index global."
        ),
    )

    add_root_argument(index_parser)

    index_parser.add_argument(
        "--output",
        help=(
            "Chemin de sortie personnalisé."
        ),
    )

    index_parser.set_defaults(
        handler=command_index
    )

    download_daf_parser = (
        subparsers.add_parser(
            "download-daf",
            help=(
                "Télécharger un daf sans "
                "l’enregistrer."
            ),
        )
    )

    download_daf_parser.add_argument(
        "commentary",
        help=(
            "Clé ou nom du commentaire, "
            "par exemple ritva."
        ),
    )

    download_daf_parser.add_argument(
        "masechet",
        help=(
            "Nom anglais du traité, "
            "par exemple Taanit."
        ),
    )

    download_daf_parser.add_argument(
        "daf",
        help=(
            "Daf à télécharger, par exemple 2a."
        ),
    )

    add_root_argument(download_daf_parser)
    add_network_arguments(download_daf_parser)

    download_daf_parser.add_argument(
        "--sefaria-title",
        help=(
            "Titre Sefaria personnalisé."
        ),
    )

    download_daf_parser.add_argument(
        "--show-text",
        action="store_true",
        help=(
            "Afficher le texte des commentaires."
        ),
    )

    download_daf_parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help=(
            "Nombre de commentaires affichés "
            "avec --show-text."
        ),
    )

    download_daf_parser.set_defaults(
        handler=command_download_daf
    )

    download_parser = subparsers.add_parser(
        "download",
        help=(
            "Télécharger et enregistrer un traité "
            "ou plusieurs dapim."
        ),
    )

    download_parser.add_argument(
        "commentary",
        help=(
            "Clé ou nom du commentaire."
        ),
    )

    download_parser.add_argument(
        "masechet",
        help=(
            "Nom anglais du traité."
        ),
    )

    add_root_argument(download_parser)
    add_network_arguments(download_parser)

    download_parser.add_argument(
        "--daf",
        action="append",
        help=(
            "Daf précis. Répéter l’option pour "
            "plusieurs dapim."
        ),
    )

    download_parser.add_argument(
        "--start",
        default="2a",
        help=(
            "Premier daf lorsque --daf n’est pas "
            "utilisé."
        ),
    )

    download_parser.add_argument(
        "--end",
        help=(
            "Dernier daf lorsque --daf n’est pas "
            "utilisé."
        ),
    )

    download_parser.add_argument(
        "--destination",
        help=(
            "Fichier JSON de destination."
        ),
    )

    download_parser.add_argument(
        "--sefaria-title",
        help=(
            "Titre Sefaria personnalisé."
        ),
    )

    download_parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Retélécharger les dapim déjà présents."
        ),
    )

    download_parser.add_argument(
        "--keep-empty",
        action="store_true",
        help=(
            "Enregistrer aussi les dapim sans "
            "commentaire."
        ),
    )

    download_parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help=(
            "Arrêter au premier daf en échec."
        ),
    )

    download_parser.add_argument(
        "--no-backup",
        action="store_true",
        help=(
            "Ne pas créer de sauvegarde."
        ),
    )

    download_parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help=(
            "Reconstruire l’index après le "
            "téléchargement."
        ),
    )

    download_parser.set_defaults(
        handler=command_download
    )

    import_file_parser = (
        subparsers.add_parser(
            "import-file",
            help=(
                "Importer un fichier JSON local."
            ),
        )
    )

    import_file_parser.add_argument(
        "source",
        help=(
            "Fichier JSON à importer."
        ),
    )

    add_root_argument(import_file_parser)
    add_network_arguments(import_file_parser)

    import_file_parser.add_argument(
        "--destination",
        help=(
            "Chemin de destination personnalisé."
        ),
    )

    import_file_parser.add_argument(
        "--no-backup",
        action="store_true",
        help=(
            "Ne pas créer de sauvegarde."
        ),
    )

    import_file_parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help=(
            "Reconstruire l’index après l’import."
        ),
    )

    import_file_parser.set_defaults(
        handler=command_import_file
    )

    import_directory_parser = (
        subparsers.add_parser(
            "import-directory",
            help=(
                "Importer tous les JSON d’un dossier."
            ),
        )
    )

    import_directory_parser.add_argument(
        "source",
        help=(
            "Dossier source."
        ),
    )

    add_root_argument(import_directory_parser)
    add_network_arguments(
        import_directory_parser
    )

    import_directory_parser.add_argument(
        "--pattern",
        default="*.json",
        help=(
            "Motif de fichiers à importer."
        ),
    )

    import_directory_parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help=(
            "Reconstruire l’index après l’import."
        ),
    )

    import_directory_parser.set_defaults(
        handler=command_import_directory
    )

    checkpoint_parser = (
        subparsers.add_parser(
            "checkpoint",
            help=(
                "Afficher l’état d’un checkpoint."
            ),
        )
    )

    checkpoint_parser.add_argument(
        "commentary",
        help="Clé du commentaire.",
    )

    checkpoint_parser.add_argument(
        "masechet",
        help="Nom du traité.",
    )

    checkpoint_parser.add_argument(
        "--checkpoint-root",
        default=str(DEFAULT_CHECKPOINT_ROOT),
        help=(
            "Racine des checkpoints."
        ),
    )

    checkpoint_parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Afficher le checkpoint en JSON."
        ),
    )

    checkpoint_parser.add_argument(
        "--show-pending",
        action="store_true",
        help=(
            "Afficher les éléments à reprendre."
        ),
    )

    checkpoint_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help=(
            "Nombre maximal d’éléments à afficher."
        ),
    )

    checkpoint_parser.set_defaults(
        handler=command_checkpoint
    )

    reset_parser = subparsers.add_parser(
        "checkpoint-reset-processing",
        help=(
            "Remettre les entrées processing "
            "à pending."
        ),
    )

    reset_parser.add_argument(
        "commentary",
        help="Clé du commentaire.",
    )

    reset_parser.add_argument(
        "masechet",
        help="Nom du traité.",
    )

    reset_parser.add_argument(
        "--checkpoint-root",
        default=str(DEFAULT_CHECKPOINT_ROOT),
        help=(
            "Racine des checkpoints."
        ),
    )

    reset_parser.set_defaults(
        handler=command_checkpoint_reset_processing
    )

    delete_parser = subparsers.add_parser(
        "checkpoint-delete",
        help=(
            "Supprimer un checkpoint."
        ),
    )

    delete_parser.add_argument(
        "commentary",
        help="Clé du commentaire.",
    )

    delete_parser.add_argument(
        "masechet",
        help="Nom du traité.",
    )

    delete_parser.add_argument(
        "--checkpoint-root",
        default=str(DEFAULT_CHECKPOINT_ROOT),
        help=(
            "Racine des checkpoints."
        ),
    )

    delete_parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Confirmer la suppression."
        ),
    )

    delete_parser.set_defaults(
        handler=command_checkpoint_delete
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    handler = getattr(
        args,
        "handler",
        None,
    )

    if handler is None:
        parser.print_help()
        return 1

    try:
        return int(handler(args))

    except KeyboardInterrupt:
        print()
        print(
            "⛔ Opération interrompue par "
            "l’utilisateur.",
            file=sys.stderr,
        )
        return 130

    except (
        CommentaryCLIError,
        CommentaryDownloadError,
        CommentaryCheckpointError,
        ValueError,
    ) as exc:
        print(
            f"❌ {exc}",
            file=sys.stderr,
        )
        return 2

    except Exception as exc:
        print(
            f"❌ Erreur inattendue : {exc}",
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
