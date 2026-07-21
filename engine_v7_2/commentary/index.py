from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .loader import CommentaryLoader
from .models import CommentaryDocument
from .registry import get_commentary


def _utc_now_iso() -> str:
    """
    Retourne la date UTC actuelle au format ISO 8601.
    """

    return datetime.now(timezone.utc).isoformat()


def _normalize_name(value: str) -> str:
    """
    Normalise un nom pour les comparaisons internes.
    """

    return (
        value.strip()
        .lower()
        .replace("_", "-")
        .replace(" ", "-")
    )


@dataclass
class CommentaryFileIndex:
    """
    Entrée d’index correspondant à un fichier de commentaire.
    """

    path: str
    commentary_key: str
    commentary: str
    priority: int
    masechet: str
    source: str
    version: str
    dapim: list[str] = field(default_factory=list)
    daf_count: int = 0
    comment_count: int = 0
    translated_fr_count: int = 0
    valid: bool = True
    error_count: int = 0
    warning_count: int = 0
    file_size: int = 0
    modified_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "commentary_key": self.commentary_key,
            "commentary": self.commentary,
            "priority": self.priority,
            "masechet": self.masechet,
            "source": self.source,
            "version": self.version,
            "dapim": list(self.dapim),
            "daf_count": self.daf_count,
            "comment_count": self.comment_count,
            "translated_fr_count": self.translated_fr_count,
            "valid": self.valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "file_size": self.file_size,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "CommentaryFileIndex":
        return cls(
            path=str(payload.get("path") or ""),
            commentary_key=str(
                payload.get("commentary_key") or ""
            ),
            commentary=str(
                payload.get("commentary") or ""
            ),
            priority=int(payload.get("priority") or 0),
            masechet=str(payload.get("masechet") or ""),
            source=str(payload.get("source") or ""),
            version=str(payload.get("version") or ""),
            dapim=[
                str(value)
                for value in payload.get("dapim", [])
            ],
            daf_count=int(payload.get("daf_count") or 0),
            comment_count=int(
                payload.get("comment_count") or 0
            ),
            translated_fr_count=int(
                payload.get("translated_fr_count") or 0
            ),
            valid=bool(payload.get("valid", True)),
            error_count=int(
                payload.get("error_count") or 0
            ),
            warning_count=int(
                payload.get("warning_count") or 0
            ),
            file_size=int(payload.get("file_size") or 0),
            modified_at=str(
                payload.get("modified_at") or ""
            ),
        )


@dataclass
class CommentaryIndexError:
    """
    Fichier qui n’a pas pu être indexé.
    """

    path: str
    error: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "error": self.error,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "CommentaryIndexError":
        return cls(
            path=str(payload.get("path") or ""),
            error=str(payload.get("error") or ""),
        )


@dataclass
class CommentaryIndex:
    """
    Index global de tous les commentaires disponibles.
    """

    version: str = "1.0"
    generated_at: str = field(
        default_factory=_utc_now_iso
    )
    root: str = "public/data/commentaries"
    files: list[CommentaryFileIndex] = field(
        default_factory=list
    )
    errors: list[CommentaryIndexError] = field(
        default_factory=list
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "root": self.root,
            "statistics": self.statistics(),
            "commentaries": self.commentary_statistics(),
            "masechtot": self.masechet_statistics(),
            "files": [
                entry.to_dict()
                for entry in self.files
            ],
            "errors": [
                error.to_dict()
                for error in self.errors
            ],
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "CommentaryIndex":
        if not isinstance(payload, dict):
            raise TypeError(
                "L’index doit être représenté par un objet JSON."
            )

        return cls(
            version=str(payload.get("version") or "1.0"),
            generated_at=str(
                payload.get("generated_at") or ""
            ),
            root=str(
                payload.get("root")
                or "public/data/commentaries"
            ),
            files=[
                CommentaryFileIndex.from_dict(entry)
                for entry in payload.get("files", [])
                if isinstance(entry, dict)
            ],
            errors=[
                CommentaryIndexError.from_dict(entry)
                for entry in payload.get("errors", [])
                if isinstance(entry, dict)
            ],
        )

    def statistics(self) -> dict[str, Any]:
        """
        Statistiques générales de l’index.
        """

        commentary_keys = {
            entry.commentary_key
            for entry in self.files
            if entry.commentary_key
        }

        masechtot = {
            entry.masechet
            for entry in self.files
            if entry.masechet
        }

        daf_pairs = {
            (
                entry.commentary_key,
                entry.masechet,
                daf,
            )
            for entry in self.files
            for daf in entry.dapim
        }

        return {
            "files": len(self.files),
            "valid_files": sum(
                1
                for entry in self.files
                if entry.valid
            ),
            "invalid_files": sum(
                1
                for entry in self.files
                if not entry.valid
            ),
            "unreadable_files": len(self.errors),
            "commentaries": len(commentary_keys),
            "masechtot": len(masechtot),
            "commentary_dapim": len(daf_pairs),
            "comments": sum(
                entry.comment_count
                for entry in self.files
            ),
            "translated_fr": sum(
                entry.translated_fr_count
                for entry in self.files
            ),
            "warnings": sum(
                entry.warning_count
                for entry in self.files
            ),
            "errors": sum(
                entry.error_count
                for entry in self.files
            ),
            "total_size": sum(
                entry.file_size
                for entry in self.files
            ),
        }

    def commentary_statistics(
        self,
    ) -> dict[str, dict[str, Any]]:
        """
        Statistiques regroupées par commentaire.
        """

        result: dict[str, dict[str, Any]] = {}

        for entry in self.files:
            key = entry.commentary_key or "unknown"

            if key not in result:
                result[key] = {
                    "commentary_key": key,
                    "commentary": entry.commentary,
                    "priority": entry.priority,
                    "files": 0,
                    "masechtot": [],
                    "dapim": 0,
                    "comments": 0,
                    "translated_fr": 0,
                    "valid_files": 0,
                    "invalid_files": 0,
                }

            stats = result[key]

            stats["files"] += 1
            stats["dapim"] += entry.daf_count
            stats["comments"] += entry.comment_count
            stats["translated_fr"] += (
                entry.translated_fr_count
            )

            if entry.valid:
                stats["valid_files"] += 1
            else:
                stats["invalid_files"] += 1

            if entry.masechet not in stats["masechtot"]:
                stats["masechtot"].append(
                    entry.masechet
                )

        for stats in result.values():
            stats["masechtot"].sort(
                key=lambda value: value.lower()
            )

        return dict(
            sorted(
                result.items(),
                key=lambda item: (
                    -int(item[1].get("priority", 0)),
                    item[0],
                ),
            )
        )

    def masechet_statistics(
        self,
    ) -> dict[str, dict[str, Any]]:
        """
        Statistiques regroupées par traité.
        """

        result: dict[str, dict[str, Any]] = {}

        for entry in self.files:
            key = entry.masechet or "Unknown"

            if key not in result:
                result[key] = {
                    "masechet": key,
                    "commentaries": [],
                    "files": 0,
                    "dapim": 0,
                    "comments": 0,
                    "translated_fr": 0,
                }

            stats = result[key]

            stats["files"] += 1
            stats["dapim"] += entry.daf_count
            stats["comments"] += entry.comment_count
            stats["translated_fr"] += (
                entry.translated_fr_count
            )

            if (
                entry.commentary_key
                not in stats["commentaries"]
            ):
                stats["commentaries"].append(
                    entry.commentary_key
                )

        for stats in result.values():
            stats["commentaries"].sort()

        return dict(
            sorted(
                result.items(),
                key=lambda item: item[0].lower(),
            )
        )

    def find(
        self,
        *,
        commentary: str | None = None,
        masechet: str | None = None,
        daf: str | None = None,
        valid_only: bool = False,
    ) -> list[CommentaryFileIndex]:
        """
        Recherche des entrées dans l’index.
        """

        commentary_normalized = (
            _normalize_name(commentary)
            if commentary
            else ""
        )

        masechet_normalized = (
            _normalize_name(masechet)
            if masechet
            else ""
        )

        daf_normalized = (
            daf.strip().lower()
            if daf
            else ""
        )

        results: list[CommentaryFileIndex] = []

        for entry in self.files:
            if valid_only and not entry.valid:
                continue

            if commentary_normalized:
                entry_commentary_values = {
                    _normalize_name(
                        entry.commentary_key
                    ),
                    _normalize_name(
                        entry.commentary
                    ),
                }

                if (
                    commentary_normalized
                    not in entry_commentary_values
                ):
                    continue

            if masechet_normalized:
                if (
                    _normalize_name(entry.masechet)
                    != masechet_normalized
                ):
                    continue

            if daf_normalized:
                normalized_dapim = {
                    value.strip().lower()
                    for value in entry.dapim
                }

                if daf_normalized not in normalized_dapim:
                    continue

            results.append(entry)

        return sorted(
            results,
            key=lambda entry: (
                -entry.priority,
                entry.commentary.lower(),
                entry.masechet.lower(),
            ),
        )

    def available_commentaries(
        self,
        masechet: str,
        daf: str | None = None,
    ) -> list[str]:
        """
        Retourne les clés des commentaires disponibles.
        """

        entries = self.find(
            masechet=masechet,
            daf=daf,
            valid_only=True,
        )

        keys: list[str] = []

        for entry in entries:
            if entry.commentary_key not in keys:
                keys.append(entry.commentary_key)

        return keys


class CommentaryIndexer:
    """
    Construit et sauvegarde l’index global.
    """

    def __init__(
        self,
        root: str | Path = "public/data/commentaries",
        *,
        validate: bool = True,
        include_invalid_files: bool = True,
    ) -> None:
        self.root = Path(root)
        self.validate = validate
        self.include_invalid_files = include_invalid_files

        self.loader = CommentaryLoader(
            root=self.root,
            validate=validate,
            strict_validation=False,
        )

    def discover_files(self) -> list[Path]:
        """
        Retourne tous les fichiers JSON de commentaires.

        Le fichier d’index lui-même est ignoré.
        """

        if not self.root.exists():
            return []

        ignored_names = {
            "index.json",
            "commentary-index.json",
            "commentaries-index.json",
        }

        return sorted(
            [
                path
                for path in self.root.rglob("*.json")
                if path.is_file()
                and path.name.lower()
                not in ignored_names
            ],
            key=lambda path: str(path),
        )

    def build(
        self,
        paths: Iterable[str | Path] | None = None,
    ) -> CommentaryIndex:
        """
        Construit l’index en mémoire.
        """

        index = CommentaryIndex(
            root=str(self.root),
        )

        source_paths = (
            [Path(path) for path in paths]
            if paths is not None
            else self.discover_files()
        )

        for path in source_paths:
            try:
                entry = self._index_file(path)

                if (
                    entry.valid
                    or self.include_invalid_files
                ):
                    index.files.append(entry)

            except Exception as exc:
                index.errors.append(
                    CommentaryIndexError(
                        path=str(path),
                        error=str(exc),
                    )
                )

        index.files.sort(
            key=lambda entry: (
                -entry.priority,
                entry.commentary_key,
                entry.masechet.lower(),
                entry.path,
            )
        )

        return index

    def _index_file(
        self,
        path: Path,
    ) -> CommentaryFileIndex:
        """
        Indexe un fichier précis.
        """

        document = self.loader.load_file(path)

        validation = self.loader.validate_file(path)

        priority = 0

        try:
            definition = get_commentary(
                document.commentary_key
            )
            priority = definition.priority
        except KeyError:
            priority = 0

        stat = path.stat()

        modified_at = datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat()

        return CommentaryFileIndex(
            path=str(path),
            commentary_key=document.commentary_key,
            commentary=document.commentary,
            priority=priority,
            masechet=document.masechet,
            source=document.source,
            version=document.version,
            dapim=[
                daf.daf
                for daf in document.dapim
            ],
            daf_count=document.daf_count(),
            comment_count=document.comment_count(),
            translated_fr_count=(
                document.translated_fr_count()
            ),
            valid=validation.is_valid,
            error_count=len(validation.errors),
            warning_count=len(validation.warnings),
            file_size=stat.st_size,
            modified_at=modified_at,
        )

    def save(
        self,
        index: CommentaryIndex,
        path: str | Path | None = None,
    ) -> Path:
        """
        Sauvegarde l’index au format JSON.
        """

        output_path = (
            Path(path)
            if path is not None
            else self.root / "index.json"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path = output_path.with_suffix(
            output_path.suffix + ".tmp"
        )

        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                index.to_dict(),
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")

        temporary_path.replace(output_path)

        return output_path

    def build_and_save(
        self,
        path: str | Path | None = None,
    ) -> CommentaryIndex:
        """
        Construit puis sauvegarde l’index.
        """

        index = self.build()
        self.save(index, path)
        return index


def load_commentary_index(
    path: str | Path = (
        "public/data/commentaries/index.json"
    ),
) -> CommentaryIndex:
    """
    Charge un index existant.
    """

    source_path = Path(path)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Index des commentaires introuvable : {source_path}"
        )

    try:
        with source_path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(
            (
                f"Index JSON invalide, ligne {exc.lineno}, "
                f"colonne {exc.colno} : {exc.msg}"
            )
        ) from exc

    return CommentaryIndex.from_dict(payload)


def build_commentary_index(
    root: str | Path = "public/data/commentaries",
    *,
    output_path: str | Path | None = None,
) -> CommentaryIndex:
    """
    Fonction utilitaire de construction de l’index.
    """

    indexer = CommentaryIndexer(root=root)
    index = indexer.build()
    indexer.save(index, output_path)

    return index
