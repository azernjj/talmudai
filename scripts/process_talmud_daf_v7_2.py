#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


HEBREW_PATTERN = re.compile(r"[\u0590-\u05ff]")
FORBIDDEN_PATTERN = re.compile(
    r"\b(?:prêtre|prêtres|prêtrise|sacrificateur|"
    r"sacrificateurs|veille|veilles)\b",
    flags=re.IGNORECASE,
)


def run_command(
    command: list[str],
    *,
    project_root: Path,
) -> None:
    print("\n$", " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=project_root,
        check=False,
    )

    if completed.returncode:
        raise SystemExit(completed.returncode)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise TypeError(
            f"{path} ne contient pas un objet JSON."
        )

    return payload


def resolve_daf(
    document: dict[str, Any],
    daf_name: str,
) -> dict[str, Any]:
    dapim = document.get("dapim")

    if not isinstance(dapim, dict):
        raise ValueError("La clé dapim est absente.")

    daf = dapim.get(daf_name)

    if not isinstance(daf, dict):
        raise ValueError(
            f"Le daf {daf_name!r} est introuvable."
        )

    segments = daf.get("segments")

    if not isinstance(segments, list) or not segments:
        raise ValueError(
            f"Aucun segment détecté pour {daf_name}."
        )

    return daf


def commentary_summary(
    study: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    commentaries = study.get("commentaries")

    if not isinstance(commentaries, dict):
        return {}

    entry = commentaries.get(key)

    if not isinstance(entry, dict):
        return {}

    return entry


def export_review(
    *,
    corpus_path: Path,
    daf_name: str,
    output_path: Path,
) -> int:
    document = load_json(corpus_path)
    daf = resolve_daf(document, daf_name)
    segments = daf["segments"]
    masechet = str(
        document.get("title")
        or corpus_path.stem
    )

    review: dict[str, Any] = {
        "masechet": masechet,
        "daf": daf_name,
        "segments_count": len(segments),
        "segments": [],
    }

    for number, segment in enumerate(
        segments,
        start=1,
    ):
        if not isinstance(segment, dict):
            raise TypeError(
                f"Segment invalide : {daf_name}:{number}"
            )

        study = segment.get("study")

        if not isinstance(study, dict):
            study = {}

        review["segments"].append({
            "reference": (
                f"{masechet} {daf_name}:{number}"
            ),
            "segment_number": number,
            "hebrew": segment.get("he", ""),
            "english": segment.get("en", ""),
            "translation_fr": segment.get("fr", ""),
            "explanation_fr": segment.get(
                "fr_explanation",
                "",
            ),
            "rachi": commentary_summary(
                study,
                "rachi",
            ),
            "tossefot": commentary_summary(
                study,
                "tossefot",
            ),
            "translation_meta": segment.get(
                "translation_meta",
                {},
            ),
            "fr_editorial": segment.get(
                "fr_editorial",
                {},
            ),
        })

    output_path.write_text(
        json.dumps(
            review,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print(
        "\n✅ Fichier de révision créé :",
        output_path,
    )
    print("✅ Segments exportés :", len(segments))
    return len(segments)


def audit_daf(
    *,
    corpus_path: Path,
    daf_name: str,
    require_reviewed: bool,
) -> list[str]:
    document = load_json(corpus_path)
    daf = resolve_daf(document, daf_name)
    segments = daf["segments"]
    problems: list[str] = []

    if require_reviewed:
        validation = daf.get("fr_validation")

        if not isinstance(validation, dict):
            problems.append(
                "fr_validation est absent."
            )
        elif validation.get("status") != "reviewed":
            problems.append(
                "Le daf n'a pas le statut reviewed."
            )
        elif validation.get(
            "segments_reviewed"
        ) != len(segments):
            problems.append(
                "Le nombre de segments révisés est incorrect."
            )

    for number, segment in enumerate(
        segments,
        start=1,
    ):
        if not isinstance(segment, dict):
            problems.append(
                f"{daf_name}:{number} : segment invalide"
            )
            continue

        translation = str(
            segment.get("fr") or ""
        ).strip()
        explanation = str(
            segment.get("fr_explanation") or ""
        ).strip()
        rendered = str(
            segment.get("fr_html") or ""
        )
        study = segment.get("study")

        issues: list[str] = []

        if not translation:
            issues.append("traduction absente")

        if HEBREW_PATTERN.search(translation):
            issues.append(
                "hébreu présent dans la traduction"
            )

        if FORBIDDEN_PATTERN.search(translation):
            issues.append(
                "terme interdit dans la traduction"
            )

        if HEBREW_PATTERN.search(explanation):
            issues.append(
                "hébreu présent dans l'explication"
            )

        if FORBIDDEN_PATTERN.search(explanation):
            issues.append(
                "terme interdit dans l'explication"
            )

        if "<strong>" not in rendered:
            issues.append(
                "traduction non affichée en gras"
            )

        if (
            explanation
            and "talmud-explanation-section"
            not in rendered
        ):
            issues.append(
                "explication absente du HTML"
            )

        if not isinstance(study, dict):
            issues.append("study absent")
        else:
            if study.get("translation") != translation:
                issues.append(
                    "study.translation non synchronisé"
                )

            if study.get("explanation") != explanation:
                issues.append(
                    "study.explanation non synchronisé"
                )

            for key in ("rachi", "tossefot"):
                entry = commentary_summary(
                    study,
                    key,
                )
                summary = str(
                    entry.get("summary") or ""
                )

                if HEBREW_PATTERN.search(summary):
                    issues.append(
                        f"hébreu présent dans {key}"
                    )

                if FORBIDDEN_PATTERN.search(summary):
                    issues.append(
                        f"terme interdit dans {key}"
                    )

        if issues:
            problems.append(
                f"{daf_name}:{number} : "
                + "; ".join(issues)
            )

    print("\n🔎 Contrôle du daf")
    print("Segments :", len(segments))
    print("Problèmes :", len(problems))

    for problem in problems:
        print("-", problem)

    return problems


def prepare(args: argparse.Namespace) -> None:
    project_root = Path(
        args.project_root
    ).resolve()
    corpus_path = (
        project_root / args.file
    ).resolve()
    translator = (
        project_root
        / "scripts"
        / "translate_talmud_aligned_v7_2.py"
    )
    output_path = (
        project_root
        / (
            f"{corpus_path.stem}_"
            f"{args.daf}_review.json"
        )
    )

    base_command = [
        sys.executable,
        str(translator),
        "--file",
        str(corpus_path),
        "--only-daf",
        args.daf,
        "--start-segment",
        "1",
        "--limit",
        "0",
        "--model",
        args.model,
    ]

    run_command(
        [*base_command, "--dry-run"],
        project_root=project_root,
    )
    run_command(
        [*base_command, "--force"],
        project_root=project_root,
    )

    export_review(
        corpus_path=corpus_path,
        daf_name=args.daf,
        output_path=output_path,
    )
    audit_daf(
        corpus_path=corpus_path,
        daf_name=args.daf,
        require_reviewed=False,
    )

    print(
        "\n⏸️ Envoyez maintenant le fichier de "
        "révision pour la correction humaine :"
    )
    print(output_path)
    print(
        "Ne lancez finalize qu'après l'application "
        "des corrections."
    )


def finalize(args: argparse.Namespace) -> None:
    project_root = Path(
        args.project_root
    ).resolve()
    corpus_path = (
        project_root / args.file
    ).resolve()

    problems = audit_daf(
        corpus_path=corpus_path,
        daf_name=args.daf,
        require_reviewed=True,
    )

    if problems:
        raise SystemExit(
            "⛔ Finalisation refusée : "
            "corrigez les problèmes ci-dessus."
        )

    load_json(corpus_path)
    print("✅ Corpus source JSON valide")

    relative_corpus = corpus_path.relative_to(
        project_root
    )
    built_corpus = (
        project_root
        / "dist"
        / relative_corpus.relative_to("public")
    )

    if not args.skip_build:
        run_command(
            ["npm", "run", "build"],
            project_root=project_root,
        )

        if not built_corpus.is_file():
            raise SystemExit(
                f"⛔ Corpus absent du build : {built_corpus}"
            )

        load_json(built_corpus)
        print("✅ Corpus présent et valide dans dist")
    else:
        print("⏭️ Build ignoré à la demande.")

    run_command(
        ["git", "add", "--", str(relative_corpus)],
        project_root=project_root,
    )
    run_command(
        ["git", "diff", "--cached", "--stat"],
        project_root=project_root,
    )

    if not args.commit:
        print(
            "\n✅ Prêt pour le commit."
        )
        print(
            "Relancez avec --commit après avoir "
            "vérifié le diff."
        )
        return

    message = (
        args.message
        or (
            "Translate and review "
            f"{corpus_path.stem.title()} {args.daf}"
        )
    )

    run_command(
        ["git", "commit", "-m", message],
        project_root=project_root,
    )

    if args.push:
        run_command(
            ["git", "push", "origin", "main"],
            project_root=project_root,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Orchestre la traduction, la révision, "
            "le build et le commit d'un daf."
        )
    )
    subparsers = parser.add_subparsers(
        dest="action",
        required=True,
    )

    for action in ("prepare", "finalize"):
        subparser = subparsers.add_parser(action)
        subparser.add_argument(
            "--project-root",
            default=".",
        )
        subparser.add_argument(
            "--file",
            required=True,
        )
        subparser.add_argument(
            "--daf",
            required=True,
        )

        if action == "prepare":
            subparser.add_argument(
                "--model",
                default="gpt-5.4-mini",
            )
        else:
            subparser.add_argument(
                "--commit",
                action="store_true",
            )
            subparser.add_argument(
                "--push",
                action="store_true",
            )
            subparser.add_argument(
                "--message",
            )
            subparser.add_argument(
                "--skip-build",
                action="store_true",
                help=(
                    "Ne relance pas le build lorsque le même "
                    "daf vient déjà d'être finalisé."
                ),
            )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.action == "prepare":
        prepare(args)
    else:
        finalize(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
