from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .registry import get_commentary, normalize_commentary_key


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _daf_sort_key(daf: str) -> tuple[int, int, str]:
    value = _clean_text(daf).lower()

    if not value:
        return (10**9, 10**9, "")

    number_part = ""
    side_part = ""

    for character in value:
        if character.isdigit():
            number_part += character
        elif character.isalpha():
            side_part += character

    number = int(number_part) if number_part else 10**9

    if side_part.startswith("a"):
        side = 0
    elif side_part.startswith("b"):
        side = 1
    else:
        side = 2

    return (number, side, value)


@dataclass
class CommentaryComment:
    ref: str = ""
    he: str = ""
    en: str = ""
    fr: str = ""
    segment: int | str | None = None
    base_ref: str = ""
    dibur_hamatchil: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "CommentaryComment":
        if not isinstance(payload, dict):
            raise TypeError(
                "Un commentaire doit être représenté par un objet JSON."
            )

        metadata = payload.get("metadata", {})

        if not isinstance(metadata, dict):
            metadata = {}

        known_fields = {
            "ref",
            "he",
            "en",
            "fr",
            "segment",
            "base_ref",
            "dibur_hamatchil",
            "metadata",
        }

        for key, value in payload.items():
            if key not in known_fields:
                metadata.setdefault(key, value)

        return cls(
            ref=_clean_text(payload.get("ref")),
            he=_clean_text(payload.get("he")),
            en=_clean_text(payload.get("en")),
            fr=_clean_text(payload.get("fr")),
            segment=payload.get("segment"),
            base_ref=_clean_text(payload.get("base_ref")),
            dibur_hamatchil=_clean_text(
                payload.get("dibur_hamatchil")
            ),
            metadata=dict(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ref": self.ref,
            "he": self.he,
            "en": self.en,
            "fr": self.fr,
        }

        if self.segment not in (None, ""):
            payload["segment"] = self.segment

        if self.base_ref:
            payload["base_ref"] = self.base_ref

        if self.dibur_hamatchil:
            payload["dibur_hamatchil"] = self.dibur_hamatchil

        if self.metadata:
            payload["metadata"] = dict(self.metadata)

        return payload

    def has_content(self) -> bool:
        return any(
            (
                self.he.strip(),
                self.en.strip(),
                self.fr.strip(),
            )
        )

    def is_translated_fr(self) -> bool:
        return bool(self.fr.strip())


@dataclass
class CommentaryDaf:
    daf: str
    comments: list[CommentaryComment] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "CommentaryDaf":
        if not isinstance(payload, dict):
            raise TypeError(
                "Un daf doit être représenté par un objet JSON."
            )

        raw_comments = payload.get("comments", [])

        if raw_comments is None:
            raw_comments = []

        if not isinstance(raw_comments, list):
            raise TypeError(
                "Le champ 'comments' doit être une liste."
            )

        metadata = payload.get("metadata", {})

        if not isinstance(metadata, dict):
            metadata = {}

        return cls(
            daf=_clean_text(payload.get("daf")),
            comments=[
                CommentaryComment.from_dict(comment)
                for comment in raw_comments
                if isinstance(comment, dict)
            ],
            metadata=dict(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "daf": self.daf,
            "comments": [
                comment.to_dict()
                for comment in self.comments
            ],
        }

        if self.metadata:
            payload["metadata"] = dict(self.metadata)

        return payload

    def valid_comments(self) -> list[CommentaryComment]:
        return [
            comment
            for comment in self.comments
            if comment.has_content()
        ]

    def comment_count(self) -> int:
        return len(self.comments)

    def translated_fr_count(self) -> int:
        return sum(
            1
            for comment in self.comments
            if comment.is_translated_fr()
        )


@dataclass
class CommentaryDocument:
    masechet: str
    file: str
    commentary: str
    commentary_key: str
    source: str = "sefaria"
    dapim: list[CommentaryDaf] = field(default_factory=list)
    version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
        *,
        source_path: str | Path | None = None,
    ) -> "CommentaryDocument":
        if not isinstance(payload, dict):
            raise TypeError(
                "Le document de commentaire doit être un objet JSON."
            )

        path = Path(source_path) if source_path else None

        raw_commentary_key = _clean_text(
            payload.get("commentary_key")
            or payload.get("slug")
        )

        raw_commentary = _clean_text(
            payload.get("commentary")
            or payload.get("title")
        )

        if not raw_commentary_key and raw_commentary:
            raw_commentary_key = normalize_commentary_key(
                raw_commentary
            )

        if not raw_commentary_key and path is not None:
            raw_commentary_key = normalize_commentary_key(
                path.parent.name
            )

        commentary_key = normalize_commentary_key(
            raw_commentary_key
        )

        try:
            definition = get_commentary(commentary_key)
            commentary = (
                raw_commentary
                or definition.display_name
            )
        except KeyError:
            commentary = (
                raw_commentary
                or commentary_key
                or "Commentaire inconnu"
            )

        masechet = _clean_text(
            payload.get("masechet")
            or payload.get("tractate")
        )

        file_name = _clean_text(
            payload.get("file")
            or (path.name if path is not None else "")
        )

        source = _clean_text(
            payload.get("source")
            or "sefaria"
        )

        version = _clean_text(
            payload.get("version")
            or "1.0"
        )

        raw_dapim = payload.get("dapim", [])

        if raw_dapim is None:
            raw_dapim = []

        if not isinstance(raw_dapim, list):
            raise TypeError(
                "Le champ 'dapim' doit être une liste."
            )

        raw_metadata = payload.get("metadata", {})

        if not isinstance(raw_metadata, dict):
            raw_metadata = {}

        metadata = dict(raw_metadata)

        if (
            payload.get("slug")
            and not payload.get("commentary_key")
        ):
            metadata.setdefault(
                "legacy_commentary_key_field",
                "slug",
            )

        if (
            payload.get("title")
            and not payload.get("commentary")
        ):
            metadata.setdefault(
                "legacy_commentary_title_field",
                "title",
            )

        document = cls(
            masechet=masechet,
            file=file_name,
            commentary=commentary,
            commentary_key=commentary_key,
            source=source,
            dapim=[
                CommentaryDaf.from_dict(daf_payload)
                for daf_payload in raw_dapim
                if isinstance(daf_payload, dict)
            ],
            version=version,
            metadata=metadata,
        )

        document.sort_dapim()

        return document

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "masechet": self.masechet,
            "file": self.file,
            "commentary": self.commentary,
            "commentary_key": self.commentary_key,
            "source": self.source,
            "version": self.version,
            "dapim": [
                daf.to_dict()
                for daf in self.dapim
            ],
        }

        if self.metadata:
            payload["metadata"] = dict(self.metadata)

        return payload

    def get_daf(
        self,
        daf: str,
    ) -> CommentaryDaf | None:
        target = _clean_text(daf).lower()

        for daf_entry in self.dapim:
            if daf_entry.daf.strip().lower() == target:
                return daf_entry

        return None

    def has_daf(self, daf: str) -> bool:
        return self.get_daf(daf) is not None

    def add_or_replace_daf(
        self,
        daf_entry: CommentaryDaf,
    ) -> None:
        target = daf_entry.daf.strip().lower()

        for index, current in enumerate(self.dapim):
            if current.daf.strip().lower() == target:
                self.dapim[index] = daf_entry
                self.sort_dapim()
                return

        self.dapim.append(daf_entry)
        self.sort_dapim()

    def sort_dapim(self) -> None:
        self.dapim.sort(
            key=lambda entry: _daf_sort_key(entry.daf)
        )

    def daf_count(self) -> int:
        return len(self.dapim)

    def comment_count(self) -> int:
        return sum(
            daf.comment_count()
            for daf in self.dapim
        )

    def translated_fr_count(self) -> int:
        return sum(
            daf.translated_fr_count()
            for daf in self.dapim
        )

    def statistics(self) -> dict[str, Any]:
        return {
            "masechet": self.masechet,
            "commentary": self.commentary,
            "commentary_key": self.commentary_key,
            "source": self.source,
            "dapim": self.daf_count(),
            "comments": self.comment_count(),
            "translated_fr": self.translated_fr_count(),
        }
