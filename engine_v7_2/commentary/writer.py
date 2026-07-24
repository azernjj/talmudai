from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (
    CommentaryComment,
    CommentaryDaf,
    CommentaryDocument,
)


class CommentaryWriterError(RuntimeError):
    """
    Erreur rencontrée lors de l’écriture d’un fichier de commentaire.
    """


@dataclass
class CommentaryWriteResult:
    """
    Résultat d’une opération d’écriture.
    """

    path: Path
    written: bool
    backup_path: Path | None = None
    bytes_written: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "written": self.written,
            "backup_path": None,
            "bytes_written": self.bytes_written,
            "message": self.message,
        }


class CommentaryWriter:
    """
    Écrit et met à jour les fichiers JSON de commentaires.

    L’écriture est atomique :

    1. le nouveau JSON est écrit dans un fichier temporaire ;
    2. le fichier temporaire est validé ;
    3. le fichier temporaire remplace le fichier final.

    Cela évite de perdre un fichier JSON en cas d’interruption, sans
    produire de copie .bak.

    Les paramètres historiques `create_backups`, `backup_directory` et
    `backup` sont conservés dans les signatures pour ne pas casser les
    autres composants du moteur V7.2. Ils sont volontairement ignorés :
    ce writer ne crée jamais de sauvegarde.
    """

    def __init__(
        self,
        *,
        ensure_ascii: bool = False,
        indent: int = 2,
        create_backups: bool = False,
        backup_directory: str | Path | None = None,
    ) -> None:
        self.ensure_ascii = ensure_ascii
        self.indent = indent
        self.create_backups = False
        self.backup_directory = None

    def save_document(
        self,
        document: CommentaryDocument,
        path: str | Path | None = None,
        *,
        backup: bool | None = None,
    ) -> CommentaryWriteResult:
        """
        Sauvegarde un document complet.

        Si `path` n’est pas fourni, le champ `document.file` est utilisé.
        """

        target_path = self._resolve_document_path(
            document=document,
            path=path,
        )

        return self.write_payload(
            document.to_dict(),
            target_path,
            backup=backup,
        )

    def write_payload(
        self,
        payload: dict[str, Any],
        path: str | Path,
        *,
        backup: bool | None = None,
    ) -> CommentaryWriteResult:
        """
        Écrit directement un dictionnaire JSON.
        """

        if not isinstance(payload, dict):
            raise CommentaryWriterError(
                "Le contenu à écrire doit être un dictionnaire."
            )

        target_path = Path(path)

        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path: Path | None = None

        try:
            json_text = json.dumps(
                payload,
                ensure_ascii=self.ensure_ascii,
                indent=self.indent,
            )

            json_text += "\n"

            temporary_path = self._write_temporary_file(
                target_path=target_path,
                content=json_text,
            )

            self._validate_json_file(temporary_path)

            os.replace(
                temporary_path,
                target_path,
            )

            temporary_path = None

            return CommentaryWriteResult(
                path=target_path,
                written=True,
                bytes_written=target_path.stat().st_size,
                message="Fichier enregistré avec succès.",
            )

        except Exception as exc:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                temporary_path.unlink()

            raise CommentaryWriterError(
                f"Impossible d’écrire {target_path}: {exc}"
            ) from exc

    def update_french_translation(
        self,
        document: CommentaryDocument,
        *,
        daf: str,
        comment_index: int,
        french_text: str,
        path: str | Path | None = None,
        backup: bool | None = None,
    ) -> CommentaryWriteResult:
        """
        Met à jour uniquement le champ français d’un commentaire.

        `comment_index` commence à zéro.
        """

        daf_entry = document.get_daf(daf)

        if daf_entry is None:
            raise CommentaryWriterError(
                f"Le daf {daf} est absent du document."
            )

        if comment_index < 0:
            raise CommentaryWriterError(
                "L’index du commentaire ne peut pas être négatif."
            )

        if comment_index >= len(daf_entry.comments):
            raise CommentaryWriterError(
                f"Le commentaire {comment_index} n’existe pas "
                f"dans le daf {daf}."
            )

        daf_entry.comments[comment_index].fr = (
            str(french_text).strip()
        )

        return self.save_document(
            document,
            path,
            backup=backup,
        )

    def update_comment(
        self,
        document: CommentaryDocument,
        *,
        daf: str,
        comment_index: int,
        comment: CommentaryComment,
        path: str | Path | None = None,
        backup: bool | None = None,
    ) -> CommentaryWriteResult:
        """
        Remplace entièrement un commentaire précis.
        """

        daf_entry = document.get_daf(daf)

        if daf_entry is None:
            raise CommentaryWriterError(
                f"Le daf {daf} est absent du document."
            )

        if comment_index < 0:
            raise CommentaryWriterError(
                "L’index du commentaire ne peut pas être négatif."
            )

        if comment_index >= len(daf_entry.comments):
            raise CommentaryWriterError(
                f"Le commentaire {comment_index} n’existe pas "
                f"dans le daf {daf}."
            )

        daf_entry.comments[comment_index] = comment

        return self.save_document(
            document,
            path,
            backup=backup,
        )

    def add_comment(
        self,
        document: CommentaryDocument,
        *,
        daf: str,
        comment: CommentaryComment,
        path: str | Path | None = None,
        backup: bool | None = None,
        create_daf: bool = True,
    ) -> CommentaryWriteResult:
        """
        Ajoute un commentaire à un daf.

        Si le daf n’existe pas et `create_daf=True`, il est créé.
        """

        daf_entry = document.get_daf(daf)

        if daf_entry is None:
            if not create_daf:
                raise CommentaryWriterError(
                    f"Le daf {daf} est absent du document."
                )

            daf_entry = CommentaryDaf(
                daf=daf,
                comments=[],
            )

            document.add_or_replace_daf(
                daf_entry
            )

        daf_entry.comments.append(comment)

        return self.save_document(
            document,
            path,
            backup=backup,
        )

    def add_or_replace_daf(
        self,
        document: CommentaryDocument,
        daf_entry: CommentaryDaf,
        *,
        path: str | Path | None = None,
        backup: bool | None = None,
    ) -> CommentaryWriteResult:
        """
        Ajoute un daf ou remplace le daf existant.
        """

        document.add_or_replace_daf(
            daf_entry
        )

        return self.save_document(
            document,
            path,
            backup=backup,
        )

    def merge_document(
        self,
        target: CommentaryDocument,
        incoming: CommentaryDocument,
        *,
        replace_existing_dapim: bool = True,
        path: str | Path | None = None,
        backup: bool | None = None,
    ) -> CommentaryWriteResult:
        """
        Fusionne deux documents du même commentaire et du même traité.

        Par défaut, les dapim du document entrant remplacent ceux déjà
        présents lorsqu’ils ont le même nom.
        """

        self._validate_merge_compatibility(
            target=target,
            incoming=incoming,
        )

        for incoming_daf in incoming.dapim:
            existing_daf = target.get_daf(
                incoming_daf.daf
            )

            if existing_daf is None:
                target.dapim.append(
                    incoming_daf
                )
                continue

            if replace_existing_dapim:
                target.add_or_replace_daf(
                    incoming_daf
                )
            else:
                existing_daf.comments.extend(
                    incoming_daf.comments
                )

        target.sort_dapim()

        merged_metadata = dict(
            target.metadata
        )

        merged_metadata.update(
            incoming.metadata
        )

        target.metadata = merged_metadata

        return self.save_document(
            target,
            path,
            backup=backup,
        )

    def save_translation_batch(
        self,
        document: CommentaryDocument,
        translations: dict[str, dict[int, str]],
        *,
        path: str | Path | None = None,
        backup: bool | None = None,
    ) -> CommentaryWriteResult:
        """
        Enregistre plusieurs traductions françaises en une seule écriture.

        Format attendu :

            {
                "2a": {
                    0: "Traduction du premier commentaire",
                    1: "Traduction du deuxième commentaire"
                },
                "2b": {
                    0: "Traduction..."
                }
            }
        """

        if not isinstance(translations, dict):
            raise CommentaryWriterError(
                "Les traductions doivent être fournies "
                "dans un dictionnaire."
            )

        for daf, daf_translations in translations.items():
            daf_entry = document.get_daf(
                daf
            )

            if daf_entry is None:
                raise CommentaryWriterError(
                    f"Le daf {daf} est absent du document."
                )

            if not isinstance(
                daf_translations,
                dict,
            ):
                raise CommentaryWriterError(
                    f"Les traductions du daf {daf} "
                    f"doivent être un dictionnaire."
                )

            for raw_index, french_text in (
                daf_translations.items()
            ):
                try:
                    comment_index = int(
                        raw_index
                    )
                except (TypeError, ValueError) as exc:
                    raise CommentaryWriterError(
                        f"Index invalide pour le daf {daf}: "
                        f"{raw_index}"
                    ) from exc

                if comment_index < 0:
                    raise CommentaryWriterError(
                        f"Index négatif pour le daf {daf}: "
                        f"{comment_index}"
                    )

                if comment_index >= len(
                    daf_entry.comments
                ):
                    raise CommentaryWriterError(
                        f"Le commentaire {comment_index} "
                        f"n’existe pas dans le daf {daf}."
                    )

                daf_entry.comments[
                    comment_index
                ].fr = str(french_text).strip()

        return self.save_document(
            document,
            path,
            backup=backup,
        )

    @staticmethod
    def load_payload(
        path: str | Path,
    ) -> dict[str, Any]:
        """
        Lit un fichier JSON sous forme de dictionnaire.
        """

        source_path = Path(path)

        if not source_path.exists():
            raise CommentaryWriterError(
                f"Fichier introuvable : {source_path}"
            )

        try:
            with source_path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise CommentaryWriterError(
                f"JSON invalide dans {source_path}: {exc}"
            ) from exc
        except OSError as exc:
            raise CommentaryWriterError(
                f"Impossible de lire {source_path}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise CommentaryWriterError(
                f"La racine JSON de {source_path} "
                f"doit être un objet."
            )

        return payload

    @staticmethod
    def _resolve_document_path(
        document: CommentaryDocument,
        path: str | Path | None,
    ) -> Path:
        if path is not None:
            return Path(path)

        if document.file:
            return Path(document.file)

        raise CommentaryWriterError(
            "Aucun chemin de sortie n’a été fourni et "
            "document.file est vide."
        )

    @staticmethod
    def _validate_merge_compatibility(
        *,
        target: CommentaryDocument,
        incoming: CommentaryDocument,
    ) -> None:
        target_masechet = (
            target.masechet.strip().lower()
        )

        incoming_masechet = (
            incoming.masechet.strip().lower()
        )

        if (
            target_masechet
            and incoming_masechet
            and target_masechet
            != incoming_masechet
        ):
            raise CommentaryWriterError(
                "Impossible de fusionner deux traités différents : "
                f"{target.masechet} / {incoming.masechet}"
            )

        target_commentary = (
            target.commentary_key.strip().lower()
        )

        incoming_commentary = (
            incoming.commentary_key.strip().lower()
        )

        if (
            target_commentary
            and incoming_commentary
            and target_commentary
            != incoming_commentary
        ):
            raise CommentaryWriterError(
                "Impossible de fusionner deux commentaires "
                "différents : "
                f"{target.commentary_key} / "
                f"{incoming.commentary_key}"
            )

    @staticmethod
    def _write_temporary_file(
        *,
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
                os.fsync(
                    handle.fileno()
                )
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
            raise CommentaryWriterError(
                f"Le fichier temporaire JSON est invalide : {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise CommentaryWriterError(
                "La racine du fichier JSON doit être un objet."
            )


def save_commentary_document(
    document: CommentaryDocument,
    path: str | Path | None = None,
    *,
    backup: bool = False,
) -> CommentaryWriteResult:
    """
    Fonction utilitaire pour sauvegarder un document.
    """

    writer = CommentaryWriter(
        create_backups=backup
    )

    return writer.save_document(
        document,
        path,
        backup=backup,
    )


def update_commentary_translation(
    document: CommentaryDocument,
    *,
    daf: str,
    comment_index: int,
    french_text: str,
    path: str | Path | None = None,
    backup: bool = False,
) -> CommentaryWriteResult:
    """
    Fonction utilitaire pour enregistrer une traduction française.
    """

    writer = CommentaryWriter(
        create_backups=backup
    )

    return writer.update_french_translation(
        document,
        daf=daf,
        comment_index=comment_index,
        french_text=french_text,
        path=path,
        backup=backup,
)
