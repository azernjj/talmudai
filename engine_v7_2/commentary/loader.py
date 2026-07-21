from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .models import (
    CommentaryComment,
    CommentaryDaf,
    CommentaryDocument,
)
from .registry import (
    CommentaryDefinition,
    get_commentary,
    list_commentaries,
    normalize_commentary_key,
)
from .validator import CommentaryValidator, ValidationReport


def _normalize_slug(value: str) -> str:
    """
    Transforme un nom de traité ou de commentaire en nom de fichier stable.

    Exemples :
        "Bava Metzia" -> "bava-metzia"
        "Pnei Yehoshoua" -> "pnei-yehoshoua"
    """

    normalized = (
        value.strip()
        .lower()
        .replace("’", "'")
        .replace("״", '"')
        .replace("_", "-")
    )

    characters: list[str] = []
    previous_dash = False

    for character in normalized:
        if character.isalnum():
            characters.append(character)
            previous_dash = False
        else:
            if not previous_dash:
                characters.append("-")
                previous_dash = True

    return "".join(characters).strip("-")


@dataclass
class LoadedDaf:
    """
    Résultat normalisé du chargement d’un daf.

    commentary_key:
        Identifiant interne du commentaire.

    commentary:
        Nom d’affichage.

    priority:
        Priorité éditoriale.

    masechet:
        Traité concerné.

    daf:
        Daf demandé.

    comments:
        Commentaires exploitables.

    source_path:
        Fichier source.

    validation:
        Rapport de validation du fichier.
    """

    commentary_key: str
    commentary: str
    priority: int
    masechet: str
    daf: str
    comments: list[CommentaryComment] = field(default_factory=list)
    source_path: str = ""
    validation: ValidationReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "commentary_key": self.commentary_key,
            "commentary": self.commentary,
            "priority": self.priority,
            "masechet": self.masechet,
            "daf": self.daf,
            "source_path": self.source_path,
            "comments": [
                comment.to_dict()
                for comment in self.comments
            ],
            "validation": (
                self.validation.to_dict()
                if self.validation
                else None
            ),
        }

    def comment_count(self) -> int:
        return len(self.comments)

    def has_content(self) -> bool:
        return bool(self.comments)


@dataclass
class CommentarySearchResult:
    """
    Résultat de recherche d’un fichier de commentaire.
    """

    commentary_key: str
    masechet: str
    candidates: list[Path] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.candidates)

    @property
    def first(self) -> Path | None:
        return self.candidates[0] if self.candidates else None


class CommentaryLoader:
    """
    Chargeur central des commentaires de TALMUD AI V7.2.
    """

    def __init__(
        self,
        root: str | Path = "public/data/commentaries",
        *,
        validate: bool = True,
        allow_unknown_commentary: bool = False,
        include_empty_comments: bool = False,
        strict_validation: bool = False,
    ) -> None:
        self.root = Path(root)
        self.validate = validate
        self.include_empty_comments = include_empty_comments
        self.strict_validation = strict_validation

        self.validator = CommentaryValidator(
            allow_unknown_commentary=allow_unknown_commentary,
            warn_empty_comments=True,
            warn_missing_refs=True,
        )

    def load_file(
        self,
        path: str | Path,
    ) -> CommentaryDocument:
        """
        Charge un fichier JSON et retourne un CommentaryDocument.

        Raises:
            FileNotFoundError:
                Si le fichier n’existe pas.

            ValueError:
                Si le JSON est invalide ou si la validation stricte échoue.
        """

        source_path = Path(path)

        if not source_path.exists():
            raise FileNotFoundError(
                f"Fichier de commentaire introuvable : {source_path}"
            )

        if not source_path.is_file():
            raise ValueError(
                f"Le chemin n’est pas un fichier : {source_path}"
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
                    f"JSON invalide dans {source_path}, "
                    f"ligne {exc.lineno}, colonne {exc.colno} : "
                    f"{exc.msg}"
                )
            ) from exc
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Le fichier n’est pas encodé en UTF-8 : {source_path}"
            ) from exc
        except OSError as exc:
            raise ValueError(
                f"Impossible de lire {source_path} : {exc}"
            ) from exc

        try:
            document = CommentaryDocument.from_dict(
                payload,
                source_path=source_path,
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(
                f"Structure invalide dans {source_path} : {exc}"
            ) from exc

        document.sort_dapim()

        if self.validate:
            report = self.validator.validate_document(
                document,
                source=str(source_path),
            )

            if self.strict_validation and not report.is_valid:
                first_error = (
                    str(report.errors[0])
                    if report.errors
                    else "Erreur de validation inconnue."
                )

                raise ValueError(
                    (
                        f"Le fichier {source_path} est invalide : "
                        f"{first_error}"
                    )
                )

        return document

    def validate_file(
        self,
        path: str | Path,
    ) -> ValidationReport:
        """
        Valide un fichier sans le charger manuellement.
        """

        return self.validator.validate_file(path)

    def find_files(
        self,
        commentary: str,
        masechet: str,
    ) -> CommentarySearchResult:
        """
        Recherche les fichiers possibles pour un commentaire et un traité.

        Les architectures prises en charge sont notamment :

            public/data/commentaries/rashi/berakhot.json

            public/data/commentaries/Rashi/berakhot.json

            public/data/commentaries/rashi_on_berakhot.json

            public/data/commentaries/rashi-berakhot.json
        """

        commentary_key = normalize_commentary_key(commentary)
        masechet_slug = _normalize_slug(masechet)

        result = CommentarySearchResult(
            commentary_key=commentary_key,
            masechet=masechet,
        )

        if not self.root.exists():
            return result

        directory_names = {
            commentary_key,
            commentary_key.replace("-", "_"),
        }

        try:
            definition = get_commentary(commentary_key)

            directory_names.add(
                _normalize_slug(definition.display_name)
            )
        except KeyError:
            definition = None

        filename_candidates = {
            f"{masechet_slug}.json",
            f"{masechet_slug.replace('-', '_')}.json",
        }

        candidate_paths: list[Path] = []

        for directory_name in directory_names:
            directory = self.root / directory_name

            if not directory.exists() or not directory.is_dir():
                continue

            for filename in filename_candidates:
                path = directory / filename

                if path.exists() and path.is_file():
                    candidate_paths.append(path)

            for path in directory.glob("*.json"):
                if _normalize_slug(path.stem) == masechet_slug:
                    candidate_paths.append(path)

        root_patterns = {
            f"{commentary_key}-{masechet_slug}.json",
            f"{commentary_key}_{masechet_slug}.json",
            f"{commentary_key}-on-{masechet_slug}.json",
            f"{commentary_key}_on_{masechet_slug}.json",
        }

        for filename in root_patterns:
            path = self.root / filename

            if path.exists() and path.is_file():
                candidate_paths.append(path)

        if not candidate_paths:
            for path in self.root.rglob("*.json"):
                path_slug = _normalize_slug(path.stem)
                parent_slug = _normalize_slug(path.parent.name)

                commentary_matches = (
                    parent_slug == commentary_key
                    or commentary_key in path_slug
                )

                masechet_matches = (
                    path_slug == masechet_slug
                    or masechet_slug in path_slug
                )

                if commentary_matches and masechet_matches:
                    candidate_paths.append(path)

        unique_candidates = sorted(
            set(candidate_paths),
            key=lambda path: (
                len(path.parts),
                len(path.name),
                str(path),
            ),
        )

        result.candidates = unique_candidates

        return result

    def find_file(
        self,
        commentary: str,
        masechet: str,
    ) -> Path | None:
        """
        Retourne le meilleur fichier trouvé, ou None.
        """

        return self.find_files(commentary, masechet).first

    def load_commentary(
        self,
        commentary: str,
        masechet: str,
    ) -> CommentaryDocument | None:
        """
        Recherche puis charge un commentaire complet pour un traité.
        """

        path = self.find_file(commentary, masechet)

        if path is None:
            return None

        return self.load_file(path)

    def load_daf(
        self,
        commentary: str,
        masechet: str,
        daf: str,
    ) -> LoadedDaf | None:
        """
        Charge un daf précis pour un commentaire donné.

        Retourne None lorsque le fichier ou le daf n’existe pas.
        """

        commentary_key = normalize_commentary_key(commentary)
        definition = get_commentary(commentary_key)

        path = self.find_file(commentary_key, masechet)

        if path is None:
            return None

        document = self.load_file(path)
        daf_entry = document.get_daf(daf)

        if daf_entry is None:
            return None

        comments = self._filter_comments(daf_entry.comments)

        validation = None

        if self.validate:
            validation = self.validator.validate_document(
                document,
                source=str(path),
            )

        return LoadedDaf(
            commentary_key=commentary_key,
            commentary=(
                document.commentary
                or definition.display_name
            ),
            priority=definition.priority,
            masechet=document.masechet or masechet,
            daf=daf_entry.daf,
            comments=comments,
            source_path=str(path),
            validation=validation,
        )

    def load_available_daf(
        self,
        masechet: str,
        daf: str,
        *,
        commentaries: Iterable[str] | None = None,
        enabled_only: bool = True,
    ) -> list[LoadedDaf]:
        """
        Charge tous les commentaires disponibles pour un daf.

        Le résultat est trié par priorité éditoriale décroissante.
        """

        if commentaries is None:
            definitions = list_commentaries(
                enabled_only=enabled_only,
            )
        else:
            definitions = [
                get_commentary(commentary)
                for commentary in commentaries
            ]

        loaded: list[LoadedDaf] = []

        for definition in definitions:
            result = self.load_daf(
                definition.key,
                masechet,
                daf,
            )

            if result is None:
                continue

            if not result.comments and not self.include_empty_comments:
                continue

            loaded.append(result)

        loaded.sort(
            key=lambda item: (
                -item.priority,
                item.commentary.lower(),
            )
        )

        return loaded

    def list_available_commentaries(
        self,
        masechet: str,
    ) -> list[CommentaryDefinition]:
        """
        Retourne les commentateurs disposant d’un fichier pour le traité.
        """

        available: list[CommentaryDefinition] = []

        for definition in list_commentaries():
            if self.find_file(definition.key, masechet):
                available.append(definition)

        return available

    def load_many_files(
        self,
        paths: Iterable[str | Path],
        *,
        ignore_errors: bool = False,
    ) -> list[CommentaryDocument]:
        """
        Charge plusieurs documents.
        """

        documents: list[CommentaryDocument] = []

        for path in paths:
            try:
                documents.append(self.load_file(path))
            except (
                FileNotFoundError,
                ValueError,
                TypeError,
            ):
                if not ignore_errors:
                    raise

        return documents

    def merge_documents(
        self,
        documents: Iterable[CommentaryDocument],
    ) -> CommentaryDocument:
        """
        Fusionne plusieurs documents du même commentaire et du même traité.

        Les dapim portant le même nom sont regroupés.
        """

        document_list = list(documents)

        if not document_list:
            raise ValueError(
                "Aucun document fourni pour la fusion."
            )

        first = document_list[0]

        merged = CommentaryDocument(
            masechet=first.masechet,
            file=first.file,
            commentary=first.commentary,
            commentary_key=first.commentary_key,
            source=first.source,
            version=first.version,
            metadata=dict(first.metadata),
        )

        daf_map: dict[str, CommentaryDaf] = {}

        for document in document_list:
            if (
                document.commentary_key
                != merged.commentary_key
            ):
                raise ValueError(
                    (
                        "Impossible de fusionner des commentaires "
                        "de types différents."
                    )
                )

            if (
                _normalize_slug(document.masechet)
                != _normalize_slug(merged.masechet)
            ):
                raise ValueError(
                    (
                        "Impossible de fusionner des traités "
                        "différents."
                    )
                )

            for daf_entry in document.dapim:
                key = daf_entry.daf.strip().lower()

                if key not in daf_map:
                    daf_map[key] = CommentaryDaf(
                        daf=daf_entry.daf,
                        comments=[],
                        metadata=dict(daf_entry.metadata),
                    )

                daf_map[key].comments.extend(
                    daf_entry.comments
                )

        for daf_entry in daf_map.values():
            daf_entry.comments = self._deduplicate_comments(
                daf_entry.comments
            )

            merged.dapim.append(daf_entry)

        merged.sort_dapim()

        return merged

    def _filter_comments(
        self,
        comments: Iterable[CommentaryComment],
    ) -> list[CommentaryComment]:
        filtered = list(comments)

        if not self.include_empty_comments:
            filtered = [
                comment
                for comment in filtered
                if comment.has_content()
            ]

        return self._deduplicate_comments(filtered)

    @staticmethod
    def _deduplicate_comments(
        comments: Iterable[CommentaryComment],
    ) -> list[CommentaryComment]:
        """
        Supprime les doublons exacts tout en conservant l’ordre.
        """

        unique: list[CommentaryComment] = []
        seen: set[
            tuple[str, str, str, str, str]
        ] = set()

        for comment in comments:
            key = (
                comment.ref.strip(),
                comment.he.strip(),
                comment.en.strip(),
                comment.fr.strip(),
                comment.base_ref.strip(),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(comment)

        return unique
