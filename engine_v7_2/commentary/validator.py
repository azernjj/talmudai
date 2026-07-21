from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import (
    CommentaryComment,
    CommentaryDaf,
    CommentaryDocument,
)
from .registry import COMMENTARY_REGISTRY, get_commentary


DAF_PATTERN = re.compile(r"^[0-9]+[ab]$", re.IGNORECASE)


@dataclass
class ValidationIssue:
    """
    Problème détecté pendant la validation.

    severity:
        error   : le document ne doit pas être considéré comme valide ;
        warning : le document reste exploitable, mais mérite une correction ;
        info    : simple information de contrôle.
    """

    severity: str
    code: str
    message: str
    location: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }

    def __str__(self) -> str:
        location = f" [{self.location}]" if self.location else ""

        symbols = {
            "error": "✗",
            "warning": "⚠",
            "info": "ℹ",
        }

        symbol = symbols.get(self.severity, "•")

        return (
            f"{symbol} {self.severity.upper()} "
            f"{self.code}{location} : {self.message}"
        )


@dataclass
class ValidationReport:
    """
    Rapport complet de validation.
    """

    source: str = ""
    issues: list[ValidationIssue] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def add(
        self,
        severity: str,
        code: str,
        message: str,
        location: str = "",
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,
                code=code,
                message=message,
                location=location,
            )
        )

    def error(
        self,
        code: str,
        message: str,
        location: str = "",
    ) -> None:
        self.add("error", code, message, location)

    def warning(
        self,
        code: str,
        message: str,
        location: str = "",
    ) -> None:
        self.add("warning", code, message, location)

    def info(
        self,
        code: str,
        message: str,
        location: str = "",
    ) -> None:
        self.add("info", code, message, location)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "error"
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "warning"
        ]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "info"
        ]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "valid": self.is_valid,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "info_count": len(self.infos),
            "statistics": self.statistics,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
        }

    def print_summary(self) -> None:
        status = "VALIDE" if self.is_valid else "INVALIDE"

        print()
        print("=" * 72)
        print(f"VALIDATION DU COMMENTAIRE : {status}")
        print("=" * 72)

        if self.source:
            print(f"Source       : {self.source}")

        if self.statistics:
            print(
                f"Traité       : "
                f"{self.statistics.get('masechet', '')}"
            )
            print(
                f"Commentaire  : "
                f"{self.statistics.get('commentary', '')}"
            )
            print(
                f"Clé          : "
                f"{self.statistics.get('commentary_key', '')}"
            )
            print(
                f"Dapim        : "
                f"{self.statistics.get('dapim', 0)}"
            )
            print(
                f"Commentaires : "
                f"{self.statistics.get('comments', 0)}"
            )
            print(
                f"Traduits FR  : "
                f"{self.statistics.get('translated_fr', 0)}"
            )

        print(f"Erreurs      : {len(self.errors)}")
        print(f"Avertissements : {len(self.warnings)}")
        print(f"Informations : {len(self.infos)}")

        if self.issues:
            print()
            print("Détails :")

            for issue in self.issues:
                print(issue)
        else:
            print()
            print("✓ Aucun problème détecté.")

        print("=" * 72)


class CommentaryValidator:
    """
    Validateur central des documents de commentaires.
    """

    def __init__(
        self,
        *,
        allow_unknown_commentary: bool = False,
        warn_empty_comments: bool = True,
        warn_missing_refs: bool = True,
    ) -> None:
        self.allow_unknown_commentary = allow_unknown_commentary
        self.warn_empty_comments = warn_empty_comments
        self.warn_missing_refs = warn_missing_refs

    def validate_document(
        self,
        document: CommentaryDocument,
        *,
        source: str = "",
    ) -> ValidationReport:
        report = ValidationReport(source=source)

        self._validate_document_identity(document, report)
        self._validate_dapim(document, report)

        report.statistics = document.statistics()

        return report

    def validate_dict(
        self,
        payload: dict[str, Any],
        *,
        source: str = "",
    ) -> ValidationReport:
        """
        Valide un dictionnaire JSON.

        Les erreurs de structure empêchant la création du modèle sont
        enregistrées dans le rapport au lieu de faire planter le programme.
        """

        report = ValidationReport(source=source)

        if not isinstance(payload, dict):
            report.error(
                "DOCUMENT_NOT_OBJECT",
                "Le document racine doit être un objet JSON.",
                "$",
            )
            return report

        try:
            document = CommentaryDocument.from_dict(
                payload,
                source_path=source or None,
            )
        except (TypeError, ValueError, KeyError) as exc:
            report.error(
                "DOCUMENT_PARSE_ERROR",
                str(exc),
                "$",
            )
            return report

        return self.validate_document(
            document,
            source=source,
        )

    def validate_file(
        self,
        path: str | Path,
    ) -> ValidationReport:
        """
        Charge et valide un fichier JSON.
        """

        source_path = Path(path)
        report = ValidationReport(source=str(source_path))

        if not source_path.exists():
            report.error(
                "FILE_NOT_FOUND",
                "Le fichier n’existe pas.",
                str(source_path),
            )
            return report

        if not source_path.is_file():
            report.error(
                "PATH_NOT_FILE",
                "Le chemin indiqué n’est pas un fichier.",
                str(source_path),
            )
            return report

        try:
            with source_path.open(
                "r",
                encoding="utf-8",
            ) as handle:
                payload = json.load(handle)
        except UnicodeDecodeError as exc:
            report.error(
                "FILE_ENCODING_ERROR",
                f"Le fichier n’est pas lisible en UTF-8 : {exc}",
                str(source_path),
            )
            return report
        except json.JSONDecodeError as exc:
            report.error(
                "INVALID_JSON",
                (
                    f"JSON invalide à la ligne {exc.lineno}, "
                    f"colonne {exc.colno} : {exc.msg}"
                ),
                str(source_path),
            )
            return report
        except OSError as exc:
            report.error(
                "FILE_READ_ERROR",
                f"Impossible de lire le fichier : {exc}",
                str(source_path),
            )
            return report

        return self.validate_dict(
            payload,
            source=str(source_path),
        )

    def _validate_document_identity(
        self,
        document: CommentaryDocument,
        report: ValidationReport,
    ) -> None:
        if not document.masechet.strip():
            report.error(
                "MISSING_MASECHET",
                "Le nom du traité est absent.",
                "masechet",
            )

        if not document.file.strip():
            report.warning(
                "MISSING_FILENAME",
                "Le nom du fichier n’est pas renseigné.",
                "file",
            )
        elif not document.file.lower().endswith(".json"):
            report.warning(
                "INVALID_FILENAME_EXTENSION",
                "Le nom du fichier ne se termine pas par .json.",
                "file",
            )

        if not document.commentary.strip():
            report.error(
                "MISSING_COMMENTARY",
                "Le nom du commentaire est absent.",
                "commentary",
            )

        if not document.commentary_key.strip():
            report.error(
                "MISSING_COMMENTARY_KEY",
                "La clé interne du commentaire est absente.",
                "commentary_key",
            )
        elif document.commentary_key not in COMMENTARY_REGISTRY:
            if self.allow_unknown_commentary:
                report.warning(
                    "UNKNOWN_COMMENTARY_KEY",
                    (
                        "La clé du commentaire n’est pas enregistrée "
                        f"dans le registre : {document.commentary_key}"
                    ),
                    "commentary_key",
                )
            else:
                report.error(
                    "UNKNOWN_COMMENTARY_KEY",
                    (
                        "La clé du commentaire n’est pas enregistrée "
                        f"dans le registre : {document.commentary_key}"
                    ),
                    "commentary_key",
                )
        else:
            definition = get_commentary(document.commentary_key)

            normalized_display = (
                document.commentary.strip().lower()
            )

            accepted_names = {
                definition.display_name.lower(),
                definition.key.lower(),
                *{
                    alias.lower()
                    for alias in definition.aliases
                },
            }

            if normalized_display not in accepted_names:
                report.warning(
                    "COMMENTARY_NAME_MISMATCH",
                    (
                        f"Le nom « {document.commentary} » ne correspond "
                        f"pas exactement à la définition "
                        f"« {definition.display_name} »."
                    ),
                    "commentary",
                )

        if not document.source.strip():
            report.warning(
                "MISSING_SOURCE",
                "La source du commentaire n’est pas renseignée.",
                "source",
            )

        if not document.version.strip():
            report.warning(
                "MISSING_VERSION",
                "La version du format n’est pas renseignée.",
                "version",
            )

        if not document.dapim:
            report.warning(
                "NO_DAPIM",
                "Le document ne contient aucun daf.",
                "dapim",
            )

    def _validate_dapim(
        self,
        document: CommentaryDocument,
        report: ValidationReport,
    ) -> None:
        seen_dapim: set[str] = set()
        previous_sort_key: tuple[int, int, str] | None = None

        for daf_index, daf in enumerate(document.dapim):
            location = f"dapim[{daf_index}]"

            normalized_daf = daf.daf.strip().lower()

            if not normalized_daf:
                report.error(
                    "MISSING_DAF",
                    "Le numéro du daf est absent.",
                    f"{location}.daf",
                )
                continue

            if not DAF_PATTERN.match(normalized_daf):
                report.error(
                    "INVALID_DAF_FORMAT",
                    (
                        f"Le daf « {daf.daf} » n’utilise pas "
                        "le format attendu : 2a, 2b, 3a, etc."
                    ),
                    f"{location}.daf",
                )

            if normalized_daf in seen_dapim:
                report.error(
                    "DUPLICATE_DAF",
                    f"Le daf {daf.daf} apparaît plusieurs fois.",
                    f"{location}.daf",
                )
            else:
                seen_dapim.add(normalized_daf)

            current_sort_key = self._daf_sort_key(normalized_daf)

            if (
                previous_sort_key is not None
                and current_sort_key < previous_sort_key
            ):
                report.warning(
                    "UNSORTED_DAPIM",
                    (
                        f"Le daf {daf.daf} n’est pas placé "
                        "dans l’ordre talmudique."
                    ),
                    f"{location}.daf",
                )

            previous_sort_key = current_sort_key

            self._validate_daf(
                document,
                daf,
                daf_index,
                report,
            )

    def _validate_daf(
        self,
        document: CommentaryDocument,
        daf: CommentaryDaf,
        daf_index: int,
        report: ValidationReport,
    ) -> None:
        daf_location = f"dapim[{daf_index}]"

        if not daf.comments:
            report.warning(
                "EMPTY_DAF",
                f"Le daf {daf.daf or '?'} ne contient aucun commentaire.",
                f"{daf_location}.comments",
            )
            return

        seen_refs: set[str] = set()
        seen_content: set[tuple[str, str, str]] = set()

        for comment_index, comment in enumerate(daf.comments):
            comment_location = (
                f"{daf_location}.comments[{comment_index}]"
            )

            self._validate_comment(
                document,
                daf,
                comment,
                comment_location,
                report,
            )

            normalized_ref = comment.ref.strip().lower()

            if normalized_ref:
                if normalized_ref in seen_refs:
                    report.warning(
                        "DUPLICATE_COMMENT_REF",
                        (
                            "Plusieurs commentaires possèdent "
                            f"la même référence : {comment.ref}"
                        ),
                        f"{comment_location}.ref",
                    )
                else:
                    seen_refs.add(normalized_ref)

            content_key = (
                comment.he.strip(),
                comment.en.strip(),
                comment.fr.strip(),
            )

            if any(content_key):
                if content_key in seen_content:
                    report.warning(
                        "DUPLICATE_COMMENT_CONTENT",
                        (
                            "Ce commentaire possède exactement "
                            "le même contenu qu’un commentaire précédent."
                        ),
                        comment_location,
                    )
                else:
                    seen_content.add(content_key)

    def _validate_comment(
        self,
        document: CommentaryDocument,
        daf: CommentaryDaf,
        comment: CommentaryComment,
        location: str,
        report: ValidationReport,
    ) -> None:
        if not comment.has_content():
            severity_method = (
                report.warning
                if self.warn_empty_comments
                else report.info
            )

            severity_method(
                "EMPTY_COMMENT",
                "Le commentaire ne contient ni hébreu, ni anglais, ni français.",
                location,
            )

        if self.warn_missing_refs and not comment.ref.strip():
            report.warning(
                "MISSING_COMMENT_REF",
                "La référence précise du commentaire est absente.",
                f"{location}.ref",
            )

        if comment.ref:
            ref_lower = comment.ref.lower()
            daf_lower = daf.daf.lower()

            if daf_lower not in ref_lower:
                report.warning(
                    "COMMENT_REF_DAF_MISMATCH",
                    (
                        f"La référence « {comment.ref} » ne semble pas "
                        f"correspondre au daf {daf.daf}."
                    ),
                    f"{location}.ref",
                )

            if document.masechet:
                masechet_lower = document.masechet.lower()

                if masechet_lower not in ref_lower:
                    report.warning(
                        "COMMENT_REF_MASECHET_MISMATCH",
                        (
                            f"La référence « {comment.ref} » ne semble pas "
                            f"correspondre au traité {document.masechet}."
                        ),
                        f"{location}.ref",
                    )

        if comment.base_ref:
            base_ref_lower = comment.base_ref.lower()

            if daf.daf.lower() not in base_ref_lower:
                report.warning(
                    "BASE_REF_DAF_MISMATCH",
                    (
                        f"La référence de base « {comment.base_ref} » "
                        f"ne semble pas correspondre au daf {daf.daf}."
                    ),
                    f"{location}.base_ref",
                )

            if (
                document.masechet
                and document.masechet.lower() not in base_ref_lower
            ):
                report.warning(
                    "BASE_REF_MASECHET_MISMATCH",
                    (
                        f"La référence de base « {comment.base_ref} » "
                        f"ne semble pas correspondre au traité "
                        f"{document.masechet}."
                    ),
                    f"{location}.base_ref",
                )

        if comment.fr and not comment.he and not comment.en:
            report.info(
                "FRENCH_ONLY_COMMENT",
                (
                    "Le commentaire possède une traduction française, "
                    "mais aucun texte source hébreu ou anglais."
                ),
                location,
            )

        if comment.dibur_hamatchil and not comment.he:
            report.info(
                "DIBUR_WITHOUT_HEBREW",
                (
                    "Un dibour hamat'hil est présent, "
                    "mais le texte hébreu est absent."
                ),
                f"{location}.dibur_hamatchil",
            )

    @staticmethod
    def _daf_sort_key(daf: str) -> tuple[int, int, str]:
        normalized = daf.strip().lower()

        match = re.match(r"^([0-9]+)([ab])$", normalized)

        if not match:
            return 999999, 9, normalized

        number = int(match.group(1))
        side = 0 if match.group(2) == "a" else 1

        return number, side, normalized


def validate_commentary_file(
    path: str | Path,
    *,
    allow_unknown_commentary: bool = False,
    warn_empty_comments: bool = True,
    warn_missing_refs: bool = True,
) -> ValidationReport:
    """
    Fonction utilitaire pour valider directement un fichier.
    """

    validator = CommentaryValidator(
        allow_unknown_commentary=allow_unknown_commentary,
        warn_empty_comments=warn_empty_comments,
        warn_missing_refs=warn_missing_refs,
    )

    return validator.validate_file(path)
