from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .english_source import clean_source_html


@dataclass
class AlignedCommentary:
    commentary: str
    ref: str
    base_ref: str
    hebrew: str
    english: str
    existing_french: str

    @property
    def has_english(self) -> bool:
        return bool(self.english.strip())


class AlignedCommentaryLibrary:
    """
    Indexe Rachi et Tossefot selon leur base_ref exacte.

    Aucune entrée d'un autre segment ou d'un autre daf ne peut être
    transmise au modèle.
    """

    COMMENTARIES = (
        "rachi",
        "tossefot",
    )

    def __init__(
        self,
        project_root: str | Path,
        masechet: str,
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()

        self.masechet = (
            str(masechet)
            .strip()
            .lower()
            .replace("_", "-")
        )

        if not self.masechet:
            raise ValueError(
                "Le nom du traité est vide."
            )

        self.indexes: dict[
            str,
            dict[str, list[AlignedCommentary]],
        ] = {}

        for commentary in self.COMMENTARIES:
            self.indexes[commentary] = (
                self._load_commentary(
                    commentary
                )
            )

    def _resolve_path(
        self,
        commentary: str,
    ) -> Path:
        directory = (
            self.project_root
            / "public"
            / "data"
            / "commentaries"
            / commentary
        )

        candidates = [
            path
            for path in directory.glob(
                "*.json"
            )
            if (
                path.stem
                .strip()
                .lower()
                .replace("_", "-")
                == self.masechet
            )
        ]

        if not candidates:
            raise FileNotFoundError(
                f"Fichier {commentary} introuvable "
                f"pour {self.masechet}."
            )

        if len(candidates) > 1:
            raise RuntimeError(
                f"Plusieurs fichiers {commentary} "
                f"trouvés pour {self.masechet}."
            )

        return candidates[0]

    def _load_commentary(
        self,
        commentary: str,
    ) -> dict[str, list[AlignedCommentary]]:
        path = self._resolve_path(
            commentary
        )

        document = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(document, dict):
            raise TypeError(
                f"Format invalide : {path}"
            )

        index: dict[
            str,
            list[AlignedCommentary],
        ] = {}

        dapim = document.get(
            "dapim",
            [],
        )

        if not isinstance(dapim, list):
            return index

        for daf_entry in dapim:
            if not isinstance(
                daf_entry,
                dict,
            ):
                continue

            comments = daf_entry.get(
                "comments",
                [],
            )

            if not isinstance(comments, list):
                continue

            for comment in comments:
                if not isinstance(
                    comment,
                    dict,
                ):
                    continue

                base_ref = str(
                    comment.get(
                        "base_ref",
                        "",
                    )
                ).strip()

                if not base_ref:
                    continue

                entry = AlignedCommentary(
                    commentary=commentary,
                    ref=str(
                        comment.get(
                            "ref",
                            "",
                        )
                    ).strip(),
                    base_ref=base_ref,
                    hebrew=clean_source_html(
                        comment.get(
                            "he",
                            "",
                        )
                    ),
                    english=clean_source_html(
                        comment.get(
                            "en",
                            "",
                        )
                    ),
                    existing_french=(
                        clean_source_html(
                            comment.get(
                                "fr",
                                "",
                            )
                        )
                    ),
                )

                if not (
                    entry.hebrew
                    or entry.english
                    or entry.existing_french
                ):
                    continue

                index.setdefault(
                    base_ref,
                    [],
                ).append(entry)

        return index

    def for_segment(
        self,
        daf: str,
        segment_number: int,
    ) -> dict[str, list[AlignedCommentary]]:
        base_ref = (
            f"{self.masechet.title()} "
            f"{daf}:{segment_number}"
        )

        return {
            commentary: list(
                self.indexes[
                    commentary
                ].get(
                    base_ref,
                    [],
                )
            )
            for commentary in self.COMMENTARIES
        }
