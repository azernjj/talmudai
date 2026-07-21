from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


class CommentaryCheckpointError(RuntimeError):
    """
    Erreur liée à la lecture ou à l’écriture d’un checkpoint.
    """


def utc_now_iso() -> str:
    """
    Retourne la date UTC actuelle au format ISO 8601.
    """

    return datetime.now(timezone.utc).isoformat()


def normalize_checkpoint_key(value: Any) -> str:
    """
    Normalise une valeur utilisée dans une clé de progression.
    """

    return str(value or "").strip().lower()


@dataclass
class CommentaryCheckpointItem:
    """
    État de traduction d’un commentaire individuel.
    """

    daf: str
    comment_index: int
    status: str = "pending"
    attempts: int = 0
    updated_at: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    VALID_STATUSES = {
        "pending",
        "processing",
        "completed",
        "failed",
        "skipped",
    }

    def __post_init__(self) -> None:
        self.daf = str(self.daf).strip()

        try:
            self.comment_index = int(self.comment_index)
        except (TypeError, ValueError) as exc:
            raise CommentaryCheckpointError(
                "comment_index doit être un nombre entier."
            ) from exc

        if self.comment_index < 0:
            raise CommentaryCheckpointError(
                "comment_index ne peut pas être négatif."
            )

        self.status = str(self.status).strip().lower()

        if self.status not in self.VALID_STATUSES:
            raise CommentaryCheckpointError(
                f"Statut de checkpoint invalide : {self.status}"
            )

        try:
            self.attempts = int(self.attempts)
        except (TypeError, ValueError):
            self.attempts = 0

        if self.attempts < 0:
            self.attempts = 0

        if not isinstance(self.metadata, dict):
            self.metadata = {}

    @property
    def key(self) -> str:
        return self.make_key(
            self.daf,
            self.comment_index,
        )

    @staticmethod
    def make_key(
        daf: str,
        comment_index: int,
    ) -> str:
        return (
            f"{normalize_checkpoint_key(daf)}:"
            f"{int(comment_index)}"
        )

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "CommentaryCheckpointItem":
        if not isinstance(payload, dict):
            raise CommentaryCheckpointError(
                "Une entrée de checkpoint doit être un objet JSON."
            )

        return cls(
            daf=str(payload.get("daf", "")).strip(),
            comment_index=payload.get("comment_index", 0),
            status=str(
                payload.get("status", "pending")
            ).strip(),
            attempts=payload.get("attempts", 0),
            updated_at=str(
                payload.get("updated_at", "")
            ).strip(),
            error=str(payload.get("error", "")).strip(),
            metadata=(
                dict(payload.get("metadata", {}))
                if isinstance(payload.get("metadata", {}), dict)
                else {}
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "daf": self.daf,
            "comment_index": self.comment_index,
            "status": self.status,
            "attempts": self.attempts,
            "updated_at": self.updated_at,
            "error": self.error,
        }

        if self.metadata:
            payload["metadata"] = dict(self.metadata)

        return payload

    def mark_processing(self) -> None:
        self.status = "processing"
        self.attempts += 1
        self.updated_at = utc_now_iso()
        self.error = ""

    def mark_completed(
        self,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.status = "completed"
        self.updated_at = utc_now_iso()
        self.error = ""

        if metadata:
            self.metadata.update(metadata)

    def mark_failed(
        self,
        error: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.status = "failed"
        self.updated_at = utc_now_iso()
        self.error = str(error).strip()

        if metadata:
            self.metadata.update(metadata)

    def mark_skipped(
        self,
        reason: str = "",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.status = "skipped"
        self.updated_at = utc_now_iso()
        self.error = str(reason).strip()

        if metadata:
            self.metadata.update(metadata)

    def reset(self) -> None:
        self.status = "pending"
        self.updated_at = utc_now_iso()
        self.error = ""


@dataclass
class CommentaryCheckpoint:
    """
    Checkpoint complet d’un commentaire et d’un traité.
    """

    commentary_key: str
    masechet: str
    source_file: str = ""
    destination_file: str = ""
    model: str = ""
    version: str = "1.0"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    items: dict[str, CommentaryCheckpointItem] = field(
        default_factory=dict
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.commentary_key = normalize_checkpoint_key(
            self.commentary_key
        )
        self.masechet = str(self.masechet).strip()

        if not isinstance(self.items, dict):
            self.items = {}

        if not isinstance(self.metadata, dict):
            self.metadata = {}

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "CommentaryCheckpoint":
        if not isinstance(payload, dict):
            raise CommentaryCheckpointError(
                "Le checkpoint doit être un objet JSON."
            )

        raw_items = payload.get("items", {})
        items: dict[str, CommentaryCheckpointItem] = {}

        if isinstance(raw_items, dict):
            for raw_key, raw_item in raw_items.items():
                if not isinstance(raw_item, dict):
                    continue

                item = CommentaryCheckpointItem.from_dict(
                    raw_item
                )

                items[item.key or str(raw_key)] = item

        elif isinstance(raw_items, list):
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue

                item = CommentaryCheckpointItem.from_dict(
                    raw_item
                )
                items[item.key] = item

        return cls(
            commentary_key=str(
                payload.get("commentary_key", "")
            ),
            masechet=str(payload.get("masechet", "")),
            source_file=str(
                payload.get("source_file", "")
            ),
            destination_file=str(
                payload.get("destination_file", "")
            ),
            model=str(payload.get("model", "")),
            version=str(payload.get("version", "1.0")),
            created_at=str(
                payload.get("created_at", "")
                or utc_now_iso()
            ),
            updated_at=str(
                payload.get("updated_at", "")
                or utc_now_iso()
            ),
            items=items,
            metadata=(
                dict(payload.get("metadata", {}))
                if isinstance(payload.get("metadata", {}), dict)
                else {}
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "commentary_key": self.commentary_key,
            "masechet": self.masechet,
            "source_file": self.source_file,
            "destination_file": self.destination_file,
            "model": self.model,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "items": {
                key: item.to_dict()
                for key, item in sorted(
                    self.items.items()
                )
            },
            "metadata": dict(self.metadata),
            "statistics": self.statistics(),
        }

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def get_item(
        self,
        daf: str,
        comment_index: int,
    ) -> CommentaryCheckpointItem | None:
        key = CommentaryCheckpointItem.make_key(
            daf,
            comment_index,
        )

        return self.items.get(key)

    def get_or_create_item(
        self,
        daf: str,
        comment_index: int,
    ) -> CommentaryCheckpointItem:
        key = CommentaryCheckpointItem.make_key(
            daf,
            comment_index,
        )

        item = self.items.get(key)

        if item is None:
            item = CommentaryCheckpointItem(
                daf=str(daf).strip(),
                comment_index=comment_index,
            )
            self.items[key] = item
            self.touch()

        return item

    def register_items(
        self,
        entries: Iterable[tuple[str, int]],
    ) -> int:
        """
        Enregistre les commentaires attendus dans le checkpoint.

        Retourne le nombre d’entrées nouvellement créées.
        """

        created = 0

        for daf, comment_index in entries:
            key = CommentaryCheckpointItem.make_key(
                daf,
                comment_index,
            )

            if key in self.items:
                continue

            self.items[key] = CommentaryCheckpointItem(
                daf=str(daf).strip(),
                comment_index=comment_index,
            )
            created += 1

        if created:
            self.touch()

        return created

    def mark_processing(
        self,
        daf: str,
        comment_index: int,
    ) -> CommentaryCheckpointItem:
        item = self.get_or_create_item(
            daf,
            comment_index,
        )
        item.mark_processing()
        self.touch()
        return item

    def mark_completed(
        self,
        daf: str,
        comment_index: int,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> CommentaryCheckpointItem:
        item = self.get_or_create_item(
            daf,
            comment_index,
        )
        item.mark_completed(metadata=metadata)
        self.touch()
        return item

    def mark_failed(
        self,
        daf: str,
        comment_index: int,
        error: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> CommentaryCheckpointItem:
        item = self.get_or_create_item(
            daf,
            comment_index,
        )
        item.mark_failed(
            error,
            metadata=metadata,
        )
        self.touch()
        return item

    def mark_skipped(
        self,
        daf: str,
        comment_index: int,
        reason: str = "",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> CommentaryCheckpointItem:
        item = self.get_or_create_item(
            daf,
            comment_index,
        )
        item.mark_skipped(
            reason,
            metadata=metadata,
        )
        self.touch()
        return item

    def reset_item(
        self,
        daf: str,
        comment_index: int,
    ) -> CommentaryCheckpointItem:
        item = self.get_or_create_item(
            daf,
            comment_index,
        )
        item.reset()
        self.touch()
        return item

    def should_process(
        self,
        daf: str,
        comment_index: int,
        *,
        retry_failed: bool = True,
        retry_processing: bool = True,
        force: bool = False,
    ) -> bool:
        """
        Indique si un commentaire doit être traité.

        - `completed` et `skipped` ne sont pas retraités ;
        - `failed` peut être repris ;
        - `processing` peut être repris après une interruption ;
        - `force=True` retraitre toutes les entrées.
        """

        if force:
            return True

        item = self.get_item(
            daf,
            comment_index,
        )

        if item is None:
            return True

        if item.status == "pending":
            return True

        if item.status == "failed":
            return retry_failed

        if item.status == "processing":
            return retry_processing

        return False

    def pending_items(
        self,
        *,
        retry_failed: bool = True,
        retry_processing: bool = True,
    ) -> list[CommentaryCheckpointItem]:
        return [
            item
            for item in self.items.values()
            if self.should_process(
                item.daf,
                item.comment_index,
                retry_failed=retry_failed,
                retry_processing=retry_processing,
            )
        ]

    def items_by_status(
        self,
        status: str,
    ) -> list[CommentaryCheckpointItem]:
        normalized_status = str(status).strip().lower()

        return [
            item
            for item in self.items.values()
            if item.status == normalized_status
        ]

    def statistics(self) -> dict[str, int]:
        counts = {
            "total": len(self.items),
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "attempts": 0,
        }

        for item in self.items.values():
            if item.status in counts:
                counts[item.status] += 1

            counts["attempts"] += item.attempts

        return counts

    def completion_rate(self) -> float:
        stats = self.statistics()
        total = stats["total"]

        if total == 0:
            return 0.0

        finished = (
            stats["completed"]
            + stats["skipped"]
        )

        return round(
            finished * 100.0 / total,
            2,
        )

    def is_complete(self) -> bool:
        stats = self.statistics()

        return (
            stats["total"] > 0
            and stats["pending"] == 0
            and stats["processing"] == 0
            and stats["failed"] == 0
        )


@dataclass
class CommentaryCheckpointSaveResult:
    path: Path
    written: bool
    bytes_written: int
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "written": self.written,
            "bytes_written": self.bytes_written,
            "message": self.message,
        }


class CommentaryCheckpointManager:
    """
    Gestionnaire de fichiers de checkpoint.

    Les fichiers sont stockés par défaut dans :

        checkpoints/commentaries/

    Exemple :

        checkpoints/commentaries/ritva/taanit.json
    """

    def __init__(
        self,
        root_directory: str | Path = (
            "checkpoints/commentaries"
        ),
        *,
        ensure_ascii: bool = False,
        indent: int = 2,
    ) -> None:
        self.root_directory = Path(root_directory)
        self.ensure_ascii = ensure_ascii
        self.indent = indent

    def checkpoint_path(
        self,
        commentary_key: str,
        masechet: str,
    ) -> Path:
        normalized_commentary = self._slugify(
            commentary_key
        )
        normalized_masechet = self._slugify(
            masechet
        )

        return (
            self.root_directory
            / normalized_commentary
            / f"{normalized_masechet}.json"
        )

    def create(
        self,
        *,
        commentary_key: str,
        masechet: str,
        source_file: str | Path = "",
        destination_file: str | Path = "",
        model: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CommentaryCheckpoint:
        return CommentaryCheckpoint(
            commentary_key=commentary_key,
            masechet=masechet,
            source_file=str(source_file),
            destination_file=str(destination_file),
            model=model,
            metadata=dict(metadata or {}),
        )

    def load(
        self,
        commentary_key: str,
        masechet: str,
        *,
        create_if_missing: bool = False,
        source_file: str | Path = "",
        destination_file: str | Path = "",
        model: str = "",
    ) -> CommentaryCheckpoint:
        path = self.checkpoint_path(
            commentary_key,
            masechet,
        )

        if not path.exists():
            if create_if_missing:
                return self.create(
                    commentary_key=commentary_key,
                    masechet=masechet,
                    source_file=source_file,
                    destination_file=destination_file,
                    model=model,
                )

            raise CommentaryCheckpointError(
                f"Checkpoint introuvable : {path}"
            )

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise CommentaryCheckpointError(
                f"Checkpoint JSON invalide dans {path}: {exc}"
            ) from exc
        except OSError as exc:
            raise CommentaryCheckpointError(
                f"Impossible de lire le checkpoint {path}: {exc}"
            ) from exc

        checkpoint = CommentaryCheckpoint.from_dict(
            payload
        )

        if (
            checkpoint.commentary_key
            != normalize_checkpoint_key(
                commentary_key
            )
        ):
            raise CommentaryCheckpointError(
                "Le commentaire du checkpoint ne correspond pas "
                f"à la demande : {checkpoint.commentary_key} / "
                f"{commentary_key}"
            )

        if (
            checkpoint.masechet.strip().lower()
            != str(masechet).strip().lower()
        ):
            raise CommentaryCheckpointError(
                "Le traité du checkpoint ne correspond pas "
                f"à la demande : {checkpoint.masechet} / "
                f"{masechet}"
            )

        return checkpoint

    def load_or_create(
        self,
        *,
        commentary_key: str,
        masechet: str,
        source_file: str | Path = "",
        destination_file: str | Path = "",
        model: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CommentaryCheckpoint:
        path = self.checkpoint_path(
            commentary_key,
            masechet,
        )

        if path.exists():
            checkpoint = self.load(
                commentary_key,
                masechet,
            )

            if source_file and not checkpoint.source_file:
                checkpoint.source_file = str(source_file)

            if (
                destination_file
                and not checkpoint.destination_file
            ):
                checkpoint.destination_file = str(
                    destination_file
                )

            if model:
                checkpoint.model = model

            if metadata:
                checkpoint.metadata.update(metadata)

            checkpoint.touch()

            return checkpoint

        return self.create(
            commentary_key=commentary_key,
            masechet=masechet,
            source_file=source_file,
            destination_file=destination_file,
            model=model,
            metadata=metadata,
        )

    def save(
        self,
        checkpoint: CommentaryCheckpoint,
        path: str | Path | None = None,
    ) -> CommentaryCheckpointSaveResult:
        target_path = (
            Path(path)
            if path is not None
            else self.checkpoint_path(
                checkpoint.commentary_key,
                checkpoint.masechet,
            )
        )

        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        checkpoint.touch()

        payload = checkpoint.to_dict()

        try:
            json_text = json.dumps(
                payload,
                ensure_ascii=self.ensure_ascii,
                indent=self.indent,
            )
            json_text += "\n"

            temporary_path = self._write_temporary_file(
                target_path,
                json_text,
            )

            self._validate_json_file(
                temporary_path
            )

            os.replace(
                temporary_path,
                target_path,
            )

        except Exception as exc:
            raise CommentaryCheckpointError(
                f"Impossible d’enregistrer le checkpoint "
                f"{target_path}: {exc}"
            ) from exc

        return CommentaryCheckpointSaveResult(
            path=target_path,
            written=True,
            bytes_written=target_path.stat().st_size,
            message="Checkpoint enregistré avec succès.",
        )

    def delete(
        self,
        commentary_key: str,
        masechet: str,
        *,
        missing_ok: bool = True,
    ) -> bool:
        path = self.checkpoint_path(
            commentary_key,
            masechet,
        )

        if not path.exists():
            if missing_ok:
                return False

            raise CommentaryCheckpointError(
                f"Checkpoint introuvable : {path}"
            )

        path.unlink()
        return True

    def list_checkpoints(
        self,
    ) -> list[Path]:
        if not self.root_directory.exists():
            return []

        return sorted(
            self.root_directory.rglob("*.json")
        )

    def reset_processing_items(
        self,
        checkpoint: CommentaryCheckpoint,
    ) -> int:
        """
        Replace les entrées restées en `processing` à `pending`.

        Utile après une interruption brutale du script.
        """

        reset_count = 0

        for item in checkpoint.items.values():
            if item.status != "processing":
                continue

            item.reset()
            reset_count += 1

        if reset_count:
            checkpoint.touch()

        return reset_count

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = str(value).strip().lower()

        replacements = {
            " ": "-",
            "_": "-",
            "'": "",
            "’": "",
            "/": "-",
            "\\": "-",
        }

        for source, replacement in replacements.items():
            cleaned = cleaned.replace(
                source,
                replacement,
            )

        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")

        return cleaned.strip("-") or "unknown"

    @staticmethod
    def _write_temporary_file(
        target_path: Path,
        content: str,
    ) -> Path:
        file_descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix=f".{target_path.name}.",
                suffix=".tmp",
                dir=str(target_path.parent),
                text=True,
            )
        )

        temporary_path = Path(
            temporary_name
        )

        try:
            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())

        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()

            raise

        return temporary_path

    @staticmethod
    def _validate_json_file(
        path: Path,
    ) -> None:
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except Exception as exc:
            raise CommentaryCheckpointError(
                f"Le fichier temporaire du checkpoint "
                f"est invalide : {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise CommentaryCheckpointError(
                "La racine du checkpoint doit être un objet JSON."
            )


def load_commentary_checkpoint(
    commentary_key: str,
    masechet: str,
    *,
    root_directory: str | Path = (
        "checkpoints/commentaries"
    ),
    create_if_missing: bool = False,
) -> CommentaryCheckpoint:
    manager = CommentaryCheckpointManager(
        root_directory=root_directory
    )

    return manager.load(
        commentary_key,
        masechet,
        create_if_missing=create_if_missing,
    )


def save_commentary_checkpoint(
    checkpoint: CommentaryCheckpoint,
    *,
    root_directory: str | Path = (
        "checkpoints/commentaries"
    ),
) -> CommentaryCheckpointSaveResult:
    manager = CommentaryCheckpointManager(
        root_directory=root_directory
    )

    return manager.save(checkpoint)
