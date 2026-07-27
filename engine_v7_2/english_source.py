from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


COMMENTARY_KEYS = (
    "rachi",
    "tossefot",
)


@dataclass
class EnglishSegmentSource:
    masechet: str
    daf: str
    segment_number: int
    base_ref: str
    hebrew: str
    english: str
    commentaries: dict[str, list[str]]


def clean_source_html(value: Any) -> str:
    """
    Transforme le HTML éditorial anglais en texte propre.

    Les balises de présentation sont supprimées, mais le contenu
    linguistique est conservé.
    """
    text = str(value or "")

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<sup[^>]*>.*?</sup>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(
        r"<[^>]+>",
        "",
        text,
    )

    text = html.unescape(text)
    text = text.replace("\xa0", " ")

    lines = [
        " ".join(line.split())
        for line in text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines).strip()


def _read_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def _canonical_masechet(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("_", "-")
    text = " ".join(text.split())
    return text


def _page_candidates(
    project_root: Path,
    masechet: str,
    daf: str,
) -> list[Path]:
    bavli_directory = (
        project_root
        / "public"
        / "data"
        / "bavli"
    )

    normalized = _canonical_masechet(
        masechet
    )

    candidates: list[Path] = []

    for path in bavli_directory.glob(
        f"*_{daf}.json"
    ):
        prefix = path.stem.rsplit(
            "_",
            1,
        )[0]

        if (
            _canonical_masechet(prefix)
            == normalized
        ):
            candidates.append(path)

    return sorted(candidates)


def _resolve_page_path(
    project_root: Path,
    masechet: str,
    daf: str,
) -> Path:
    candidates = _page_candidates(
        project_root,
        masechet,
        daf,
    )

    if not candidates:
        raise FileNotFoundError(
            "Fichier anglais introuvable pour "
            f"{masechet} {daf}."
        )

    if len(candidates) > 1:
        raise RuntimeError(
            "Plusieurs fichiers anglais correspondent à "
            f"{masechet} {daf} : "
            + ", ".join(
                str(path)
                for path in candidates
            )
        )

    return candidates[0]


def _commentary_path(
    project_root: Path,
    commentary: str,
    masechet: str,
) -> Path:
    directory = (
        project_root
        / "public"
        / "data"
        / "commentaries"
        / commentary
    )

    normalized = _canonical_masechet(
        masechet
    )

    candidates = [
        path
        for path in directory.glob("*.json")
        if _canonical_masechet(path.stem)
        == normalized
    ]

    if not candidates:
        raise FileNotFoundError(
            f"Fichier {commentary} introuvable "
            f"pour {masechet}."
        )

    if len(candidates) > 1:
        raise RuntimeError(
            f"Plusieurs fichiers {commentary} "
            f"correspondent à {masechet}."
        )

    return candidates[0]


def _build_commentary_index(
    path: Path,
) -> dict[str, list[str]]:
    document = _read_json(path)

    if not isinstance(document, dict):
        raise TypeError(
            f"Format de commentaire invalide : {path}"
        )

    index: dict[str, list[str]] = {}

    dapim = document.get("dapim", [])

    if not isinstance(dapim, list):
        return index

    for daf_entry in dapim:
        if not isinstance(daf_entry, dict):
            continue

        comments = daf_entry.get(
            "comments",
            [],
        )

        if not isinstance(comments, list):
            continue

        for comment in comments:
            if not isinstance(comment, dict):
                continue

            base_ref = str(
                comment.get(
                    "base_ref",
                    "",
                )
            ).strip()

            english = clean_source_html(
                comment.get(
                    "en",
                    "",
                )
            )

            if not base_ref or not english:
                continue

            index.setdefault(
                base_ref,
                [],
            ).append(english)

    return index


class EnglishSourceLibrary:
    """
    Charge les sources anglaises alignées avec le Talmud.

    Les commentaires sont sélectionnés exclusivement avec base_ref.
    Un commentaire d'un autre segment ne peut donc pas être utilisé.
    """

    def __init__(
        self,
        project_root: str | Path,
        masechet: str,
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()
        self.masechet = str(
            masechet
        ).strip()

        if not self.masechet:
            raise ValueError(
                "Le nom du traité est vide."
            )

        self.commentary_indexes: dict[
            str,
            dict[str, list[str]],
        ] = {}

        for commentary in COMMENTARY_KEYS:
            path = _commentary_path(
                self.project_root,
                commentary,
                self.masechet,
            )

            self.commentary_indexes[
                commentary
            ] = _build_commentary_index(
                path
            )

    def load_segment(
        self,
        daf: str,
        segment_number: int,
    ) -> EnglishSegmentSource:
        if segment_number < 1:
            raise ValueError(
                "segment_number doit commencer à 1."
            )

        page_path = _resolve_page_path(
            self.project_root,
            self.masechet,
            daf,
        )

        page = _read_json(page_path)

        if not isinstance(page, dict):
            raise TypeError(
                f"Format de page invalide : {page_path}"
            )

        hebrew_segments = page.get(
            "he",
            [],
        )
        english_segments = page.get(
            "text",
            [],
        )

        if not isinstance(
            hebrew_segments,
            list,
        ):
            raise TypeError(
                f"Champ he invalide : {page_path}"
            )

        if not isinstance(
            english_segments,
            list,
        ):
            raise TypeError(
                f"Champ text invalide : {page_path}"
            )

        if len(hebrew_segments) != len(
            english_segments
        ):
            raise ValueError(
                "Le nombre de segments hébreux et "
                f"anglais diffère dans {page_path}."
            )

        index = segment_number - 1

        if index >= len(english_segments):
            raise IndexError(
                f"Segment {daf}:{segment_number} "
                "hors limites."
            )

        hebrew = clean_source_html(
            hebrew_segments[index]
        )
        english = clean_source_html(
            english_segments[index]
        )

        if not hebrew:
            raise ValueError(
                f"Texte hébreu vide pour "
                f"{daf}:{segment_number}."
            )

        if not english:
            raise ValueError(
                f"Texte anglais vide pour "
                f"{daf}:{segment_number}."
            )

        base_ref = (
            f"{self.masechet} "
            f"{daf}:{segment_number}"
        )

        commentaries = {
            commentary: list(
                index_by_ref.get(
                    base_ref,
                    [],
                )
            )
            for commentary, index_by_ref
            in self.commentary_indexes.items()
        }

        return EnglishSegmentSource(
            masechet=self.masechet,
            daf=daf,
            segment_number=segment_number,
            base_ref=base_ref,
            hebrew=hebrew,
            english=english,
            commentaries=commentaries,
        )
