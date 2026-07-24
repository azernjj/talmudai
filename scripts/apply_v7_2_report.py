#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from engine_v7_2.corpus_writer import (
    apply_translation_to_segment,
    save_document,
)
from engine_v7_2.html_renderer import (
    clean_model_markdown,
    render_study_html,
)
from engine_v7_2.loader import load_document
from engine_v7_2.validator import validate_editorial_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Valide et applique au corpus un rapport TALMUD AI V7.2 "
            "déjà généré, sans nouvel appel API."
        )
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Fichier JSON du traité à modifier.",
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Rapport V7.2 à appliquer.",
    )
    return parser


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Fichier introuvable : {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON invalide dans {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"La racine JSON de {path} doit être un objet.")

    return payload


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path.resolve()


def main() -> int:
    args = build_parser().parse_args()

    corpus_path = resolve_path(args.file)
    report_path = resolve_path(args.report)
    report = read_json_object(report_path)

    final = report.get("final")
    metadata = report.get("metadata")

    if not isinstance(final, dict):
        raise SystemExit("Le rapport ne contient pas d'objet final.")

    if not isinstance(metadata, dict):
        raise SystemExit("Le rapport ne contient pas de métadonnées.")

    study = final.get("study")

    if not isinstance(study, dict):
        raise SystemExit("Le rapport ne contient pas de bloc study valide.")

    final = dict(final)
    study = dict(study)

    translation = clean_model_markdown(
        str(final.get("translation_fr", ""))
    )
    explanation = clean_model_markdown(
        str(final.get("explanation_fr", ""))
    )

    final["translation_fr"] = translation
    final["explanation_fr"] = explanation
    study["translation"] = translation
    study["explanation"] = explanation
    final["study"] = study
    final["html"] = render_study_html(study)

    available_commentaries = {
        str(name).strip()
        for name in metadata.get("commentaries_available", [])
        if str(name).strip()
    }

    validation = validate_editorial_result(
        final,
        available_commentaries=available_commentaries,
    )

    if validation.warnings:
        print("⚠️ Avertissements :")
        for warning in validation.warnings:
            print("  -", warning)

    if not validation.valid:
        print("❌ Rapport refusé :")
        for error in validation.errors:
            print("  -", error)
        return 2

    daf = str(
        report.get("daf")
        or metadata.get("daf")
        or ""
    ).strip()

    if not daf:
        raise SystemExit("Le daf est absent du rapport.")

    try:
        segment_index = int(metadata["segment_index"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(
            "segment_index est absent ou invalide dans le rapport."
        ) from exc

    document = load_document(corpus_path)

    apply_translation_to_segment(
        document=document,
        daf=daf,
        segment_index=segment_index,
        final=final,
        metadata=metadata,
    )
    save_document(corpus_path, document)

    print("✅ Rapport validé et appliqué sans appel API.")
    print("📖 Corpus :", corpus_path)
    print("📄 Rapport :", report_path)
    print("📍 Segment :", f"{daf}:{segment_index + 1}")
    print("🧩 Commentaires disponibles :", sorted(available_commentaries))
    print("📝 Taille HTML :", len(final["html"]), "caractères")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
