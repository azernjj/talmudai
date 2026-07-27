from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HEBREW_PATTERN = re.compile(r"[\u0590-\u05FF]")
HTML_PATTERN = re.compile(
    r"</?(?:b|strong|i|em|small|sup|sub|br)\b[^>]*>",
    flags=re.IGNORECASE,
)

FORBIDDEN_FRENCH_PATTERNS: tuple[
    tuple[re.Pattern[str], str],
    ...,
] = (
    (
        re.compile(
            r"\bashmou?ra\b|\bashmora\b",
            flags=re.IGNORECASE,
        ),
        "Le terme ashmora/ashmoura doit être traduit par « garde ».",
    ),
    (
        re.compile(
            r"\byaomah\b|\byomah\b",
            flags=re.IGNORECASE,
        ),
        "Le terme yoma est resté non traduit.",
    ),
    (
        re.compile(
            r"\bmise (?:effective|effectuelle|réelle) "
            r"du soleil\b",
            flags=re.IGNORECASE,
        ),
        "Calque incorrect de setting of the sun.",
    ),
    (
        re.compile(
            r"\bmise du soleil\b",
            flags=re.IGNORECASE,
        ),
        "« Mise du soleil » doit être remplacé par « coucher du soleil ».",
    ),
    (
        re.compile(
            r"\bmise en lumière\b",
            flags=re.IGNORECASE,
        ),
        "Calque anglais incorrect : « mise en lumière ».",
    ),
    (
        re.compile(
            r"\ble jour se clarifie\b",
            flags=re.IGNORECASE,
        ),
        "Dans ce contexte, le jour s’achève ou disparaît.",
    ),
    (
        re.compile(
            r"\bexpiation de la personne\b",
            flags=re.IGNORECASE,
        ),
        "Vérifier le contresens entre purification et expiation.",
    ),
    (
        re.compile(
            r"\bécoutez-en un\b",
            flags=re.IGNORECASE,
        ),
        "Calque incorrect de « שמע מינה ».",
    ),
)


@dataclass
class QualityReport:
    ref: str
    flagged: bool
    reasons: list[str]
    hebrew: str
    english: str
    french: str
    commentaries: dict[str, Any]
    confidence: float
    model: str
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _contains_phrase(
    text: str,
    phrase: str,
) -> bool:
    return phrase.casefold() in text.casefold()


def analyse_translation(
    *,
    ref: str,
    hebrew: str,
    english: str,
    french: str,
    commentaries: dict[str, Any],
    confidence: float,
    model: str,
    sample_for_review: bool = False,
) -> QualityReport:
    reasons: list[str] = []

    english_text = _normalise(english)
    french_text = _normalise(french)

    if not french_text:
        reasons.append(
            "La traduction française est vide."
        )

    if HTML_PATTERN.search(french_text):
        reasons.append(
            "La traduction française contient une balise HTML."
        )

    if HEBREW_PATTERN.search(french_text):
        reasons.append(
            "La traduction française contient du texte hébreu."
        )

    for pattern, reason in FORBIDDEN_FRENCH_PATTERNS:
        if pattern.search(french_text):
            reasons.append(reason)

    english_lower = english_text.casefold()
    french_lower = french_text.casefold()

    if "did not hear" in english_lower:
        if not any(
            expression in french_lower
            for expression in (
                "n’avaient pas entendu",
                "n'avaient pas entendu",
                "n’entendirent pas",
                "n'entendirent pas",
            )
        ):
            reasons.append(
                "L’anglais dit « did not hear », mais le français "
                "ne conserve pas clairement « ne pas entendre »."
            )

    if "purification of the person" in english_lower:
        if "purification de la personne" not in french_lower:
            reasons.append(
                "L’anglais contient « purification of the person », "
                "mais cette purification n’est pas conservée exactement."
            )

    if "emergence of the stars" in english_lower:
        if "sortie des étoiles" not in french_lower:
            reasons.append(
                "La notion de « sortie des étoiles » semble absente."
            )

    if "first watch" in english_lower:
        if "première garde" not in french_lower:
            reasons.append(
                "First watch doit être traduit par « première garde »."
            )

    if "poor person" in english_lower:
        if "pauvre" not in french_lower:
            reasons.append(
                "Poor person doit être traduit par « pauvre »."
            )

    if "setting of the sun" in english_lower:
        if "coucher" not in french_lower:
            reasons.append(
                "Setting of the sun doit être rendu par « coucher »."
            )

    if english_text and french_text:
        length_ratio = len(french_text) / len(english_text)

        if length_ratio < 0.45:
            reasons.append(
                "La traduction paraît anormalement courte "
                "par rapport à l’anglais."
            )

        if length_ratio > 2.10:
            reasons.append(
                "La traduction paraît anormalement longue "
                "par rapport à l’anglais."
            )

    try:
        numeric_confidence = float(confidence)
    except (TypeError, ValueError):
        numeric_confidence = 0.0

    if numeric_confidence < 0.60:
        reasons.append(
            "Confiance inférieure à 0,60."
        )

    if sample_for_review:
        reasons.append(
            "Segment sélectionné dans l’échantillon de contrôle."
        )

    unique_reasons: list[str] = []

    for reason in reasons:
        if reason not in unique_reasons:
            unique_reasons.append(reason)

    return QualityReport(
        ref=ref,
        flagged=bool(unique_reasons),
        reasons=unique_reasons,
        hebrew=_normalise(hebrew),
        english=english_text,
        french=french_text,
        commentaries=commentaries,
        confidence=numeric_confidence,
        model=str(model or ""),
        generated_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )


class ReviewQueue:
    def __init__(
        self,
        project_root: str | Path,
    ) -> None:
        root = Path(project_root).resolve()
        self.path = (
            root
            / ".talmud_ai_v7_2"
            / "review_queue.json"
        )
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "version": 1,
                "updated_at": None,
                "entries": [],
            }

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ):
            return {
                "version": 1,
                "updated_at": None,
                "entries": [],
            }

        if not isinstance(payload, dict):
            return {
                "version": 1,
                "updated_at": None,
                "entries": [],
            }

        if not isinstance(
            payload.get("entries"),
            list,
        ):
            payload["entries"] = []

        return payload

    def update(
        self,
        report: QualityReport,
    ) -> Path:
        payload = self._load()
        entries = payload["entries"]

        entries = [
            entry
            for entry in entries
            if not (
                isinstance(entry, dict)
                and entry.get("ref") == report.ref
            )
        ]

        if report.flagged:
            entry = report.to_dict()
            entry["status"] = "flagged"
            entries.append(entry)

        entries.sort(
            key=lambda item: str(
                item.get("ref", "")
            )
        )

        payload["version"] = 1
        payload["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()
        payload["entries"] = entries

        temporary = self.path.with_name(
            self.path.name + ".writing"
        )

        with temporary.open(
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(
            temporary,
            self.path,
        )

        return self.path
