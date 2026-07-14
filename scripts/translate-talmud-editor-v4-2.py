#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI


@dataclass
class Segment:
    node: dict[str, Any]
    daf: str
    segment_id: str
    index: int
    he: str
    old_fr: str
    prev_he: str
    next_he: str

    @property
    def ref(self) -> str:
        return f"Berakhot {self.daf}:{self.segment_id}"


def daf_sort_key(daf: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*([abAB])\s*", str(daf))
    if not match:
        return (10**9, 10**9)
    return (int(match.group(1)), 0 if match.group(2).lower() == "a" else 1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="TALMUD AI Editor V4.2 — traduction + révision indépendante"
    )
    p.add_argument("--file", required=True)
    p.add_argument("--model-translator", default="gpt-5.5")
    p.add_argument("--model-reviewer", default="gpt-5.5")
    p.add_argument("--limit", type=int)
    p.add_argument("--force", action="store_true")
    p.add_argument("--backup", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--start-daf", default="2a")
    p.add_argument("--start-segment", type=int, default=1)
    p.add_argument("--only-daf")
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--max-output-tokens", type=int, default=1800)
    p.add_argument("--charter", default="config/editorial_charter_v4_2.md")
    p.add_argument("--lexicon", default="config/lexicon_talmud_v4_2.json")
    p.add_argument("--log", default="logs/talmud_translation_v4_2.jsonl")
    return p.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Fichier introuvable : {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"JSON invalide dans {path}, ligne {exc.lineno}, colonne {exc.colno}"
        )


def atomic_save(path: Path, data: Any) -> None:
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def collect_segments(data: dict[str, Any]) -> list[Segment]:
    dapim = data.get("dapim")
    if not isinstance(dapim, dict):
        raise SystemExit("Le fichier ne contient pas un objet `dapim` valide.")

    ordered: list[tuple[str, int, dict[str, Any]]] = []
    for daf in sorted(dapim.keys(), key=daf_sort_key):
        daf_obj = dapim[daf]
        if not isinstance(daf_obj, dict):
            continue
        segments = daf_obj.get("segments", [])
        if not isinstance(segments, list):
            continue
        for index, node in enumerate(segments):
            if isinstance(node, dict) and str(node.get("he", "")).strip():
                ordered.append((str(daf), index, node))

    result: list[Segment] = []
    for pos, (daf, index, node) in enumerate(ordered):
        prev_he = str(ordered[pos - 1][2].get("he", "")).strip() if pos > 0 else ""
        next_he = (
            str(ordered[pos + 1][2].get("he", "")).strip()
            if pos + 1 < len(ordered)
            else ""
        )
        result.append(
            Segment(
                node=node,
                daf=daf,
                segment_id=str(node.get("id", index + 1)),
                index=index,
                he=str(node.get("he", "")).strip(),
                old_fr=str(node.get("fr", "")).strip(),
                prev_he=prev_he,
                next_he=next_he,
            )
        )
    return result


def select_segments(
    segments: list[Segment],
    start_daf: str,
    start_segment: int,
    only_daf: str | None,
    force: bool,
    limit: int | None,
) -> list[Segment]:
    valid_dapim = {s.daf for s in segments}
    if start_daf not in valid_dapim:
        raise SystemExit(f"Daf de départ introuvable : {start_daf}")
    if only_daf and only_daf not in valid_dapim:
        raise SystemExit(f"Daf introuvable : {only_daf}")
    if start_segment < 1:
        raise SystemExit("--start-segment doit être >= 1")

    selected: list[Segment] = []
    start_key = daf_sort_key(start_daf)

    for s in segments:
        if only_daf and s.daf != only_daf:
            continue

        if not only_daf:
            if daf_sort_key(s.daf) < start_key:
                continue
            if s.daf == start_daf:
                try:
                    sid = int(s.segment_id)
                except ValueError:
                    sid = s.index + 1
                if sid < start_segment:
                    continue

        if not force:
            meta = s.node.get("translation_meta")
            if isinstance(meta, dict) and meta.get("engine") == "talmud-ai-editor-v4-2":
                continue

        selected.append(s)

    if limit is not None:
        if limit < 1:
            raise SystemExit("--limit doit être >= 1")
        selected = selected[:limit]

    return selected


TRANSLATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fr_candidate": {"type": "string"},
        "decisions_terminologiques": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "incertitudes": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
    },
    "required": ["fr_candidate", "decisions_terminologiques", "incertitudes"],
}

REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "statut": {"type": "string", "enum": ["valide", "corrige"]},
        "fr_final": {"type": "string"},
        "corrections": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "incertitudes": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
    },
    "required": ["statut", "fr_final", "corrections", "incertitudes"],
}


def build_translation_prompt(charter: str, lexicon: dict[str, Any]) -> str:
    return f"""
Tu es le traducteur principal du comité éditorial de TALMUD AI.

Tu es spécialiste :
- de l'araméen babylonien ;
- de l'hébreu rabbinique ;
- du Talmud Bavli ;
- de la terminologie traditionnelle juive ;
- du français éditorial.

Tu traduis directement depuis l'hébreu et l'araméen.
Aucune traduction anglaise ou française existante ne t'est fournie.

OBJECTIF
Produire une traduction française complète, exacte, naturelle et publiable.

RÈGLES ABSOLUES
- Traduire tout le segment et seulement le segment.
- Ne rien inventer.
- Ne rien résumer.
- Ne pas ajouter d'explication.
- Ne pas occidentaliser la terminologie juive.
- Conserver les termes classés `termes_conserves`.
- Appliquer exactement les `traductions_obligatoires`.
- Ne jamais employer les `traductions_interdites`.
- Utiliser les segments voisins seulement pour comprendre le contexte.
- Ne jamais traduire les segments voisins.
- Conserver les répétitions et la structure argumentative de la Guemara.
- Ne produire ni HTML ni marqueurs techniques.

CHARTE
{charter}

LEXIQUE CANONIQUE
{json.dumps(lexicon, ensure_ascii=False, indent=2)}

Retourne uniquement l'objet JSON demandé.
""".strip()


def build_reviewer_prompt(charter: str, lexicon: dict[str, Any]) -> str:
    return f"""
Tu es le réviseur rabbinique et linguistique indépendant de TALMUD AI.

Tu ne dois pas approuver automatiquement la proposition du traducteur.
Tu dois la contrôler mot par mot face au texte hébreu/araméen original.

VÉRIFICATIONS OBLIGATOIRES
- aucun mot ou groupe de mots omis ;
- aucun ajout explicatif absent du texte ;
- aucun contresens ;
- aucun calque anglais ;
- aucun terme juif traditionnel traduit à tort ;
- aucune translittération utilisée à la place d'un équivalent français imposé ;
- respect exact du lexique canonique ;
- syntaxe française correcte ;
- maintien de la logique de la Guemara ;
- traduction des citations sans ajouter les développements d'autres éditions.

Si la proposition est imparfaite, corrige-la toi-même dans `fr_final`.
Seul `fr_final` sera publié.

CHARTE
{charter}

LEXIQUE CANONIQUE
{json.dumps(lexicon, ensure_ascii=False, indent=2)}

Retourne uniquement l'objet JSON demandé.
""".strip()


BAD_PATTERNS = {
    "HTML": re.compile(r"</?[a-zA-Z][^>]*>"),
    "marqueur technique": re.compile(r"TAG\d*(?:FIN)?", re.I),
    "anglais résiduel": re.compile(
        r"\b(?:the|and|with|should|would|could|rather|moreover|therefore|it)\b",
        re.I,
    ),
}


def normalize_hebrew(text: str) -> str:
    return re.sub(r"[\u0591-\u05C7]", "", text)


def validate_final(fr: str, he: str, lexicon: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not fr.strip():
        errors.append("traduction vide")

    for label, rx in BAD_PATTERNS.items():
        if rx.search(fr):
            errors.append(label)

    # Rejet global : aucune translittération de אשמורה n'est admise.
    if re.search(r"ashmou?ra|ashmura", fr, re.IGNORECASE):
        errors.append("translittération interdite : ashmoura/ashmura ; utiliser « garde »")

    if len(fr.strip()) < max(8, int(len(he) * 0.12)):
        errors.append("traduction probablement trop courte")

    he_plain = normalize_hebrew(he)
    fr_lower = fr.lower()

    # Règles canoniques groupées.
    for rule in lexicon.get("regles_canoniques", []):
        sources = rule.get("sources", [])
        if not any(normalize_hebrew(source) in he_plain for source in sources):
            continue

        required_any = [str(v).lower() for v in rule.get("required_any", [])]
        forbidden = [str(v).lower() for v in rule.get("forbidden", [])]

        if required_any and not any(value in fr_lower for value in required_any):
            errors.append(
                f"traduction canonique absente : {rule.get('label', '/'.join(sources))} "
                f"→ {' ou '.join(rule.get('required_any', []))}"
            )

        for value in forbidden:
            if value in fr_lower:
                errors.append(
                    f"traduction interdite : {rule.get('label', '/'.join(sources))} → {value}"
                )

    # Termes conservés, dédoublonnés après suppression des voyelles.
    seen_normalized: set[str] = set()
    for source, kept in lexicon.get("termes_conserves", {}).items():
        normalized_source = normalize_hebrew(source)
        if normalized_source in seen_normalized:
            continue
        seen_normalized.add(normalized_source)

        if normalized_source in he_plain and kept.lower() not in fr_lower:
            errors.append(f"terme traditionnel non conservé : {source} → {kept}")

    return errors


def append_log(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def usage_dict(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if not usage:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    return {
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
    }


def create_response(
    client: OpenAI,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int,
) -> tuple[dict[str, Any], dict[str, int]]:
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_output_tokens=max_output_tokens,
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    )
    return json.loads(response.output_text.strip()), usage_dict(response)


def translate_and_review(
    client: OpenAI,
    *,
    translator_model: str,
    reviewer_model: str,
    translator_prompt: str,
    reviewer_prompt: str,
    segment: Segment,
    lexicon: dict[str, Any],
    max_retries: int,
    max_output_tokens: int,
) -> tuple[dict[str, Any], dict[str, int]]:
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    last_error: Exception | None = None
    rejection_note = ""

    for attempt in range(1, max_retries + 1):
        try:
            translation_user = f"""
RÉFÉRENCE
{segment.ref}

CONTEXTE PRÉCÉDENT — NE PAS TRADUIRE
{segment.prev_he or "[aucun]"}

SEGMENT ACTUEL — SEUL TEXTE À TRADUIRE
{segment.he}

CONTEXTE SUIVANT — NE PAS TRADUIRE
{segment.next_he or "[aucun]"}

{rejection_note}
""".strip()

            candidate, usage1 = create_response(
                client,
                model=translator_model,
                system_prompt=translator_prompt,
                user_prompt=translation_user,
                schema_name="talmud_translation_candidate_v4",
                schema=TRANSLATION_SCHEMA,
                max_output_tokens=max_output_tokens,
            )

            review_user = f"""
RÉFÉRENCE
{segment.ref}

CONTEXTE PRÉCÉDENT — CONTEXTE UNIQUEMENT
{segment.prev_he or "[aucun]"}

TEXTE ORIGINAL À CONTRÔLER
{segment.he}

CONTEXTE SUIVANT — CONTEXTE UNIQUEMENT
{segment.next_he or "[aucun]"}

PROPOSITION DU TRADUCTEUR
{candidate["fr_candidate"]}

DÉCISIONS SIGNALÉES
{json.dumps(candidate["decisions_terminologiques"], ensure_ascii=False)}

INCERTITUDES SIGNALÉES
{json.dumps(candidate["incertitudes"], ensure_ascii=False)}

Contrôle intégralement la proposition et produis la version française finale.
""".strip()

            reviewed, usage2 = create_response(
                client,
                model=reviewer_model,
                system_prompt=reviewer_prompt,
                user_prompt=review_user,
                schema_name="talmud_translation_review_v4",
                schema=REVIEW_SCHEMA,
                max_output_tokens=max_output_tokens,
            )

            for key in totals:
                totals[key] += usage1[key] + usage2[key]

            errors = validate_final(reviewed["fr_final"], segment.he, lexicon)
            if errors:
                rejection_note = (
                    "La version précédente a été rejetée automatiquement pour : "
                    + "; ".join(errors)
                    + ". Produis une nouvelle traduction conforme."
                )
                raise ValueError("; ".join(errors))

            return {
                "candidate": candidate,
                "review": reviewed,
            }, totals

        except Exception as exc:
            last_error = exc
            message = str(exc).lower()

            if (
                "invalid_api_key" in message
                or "insufficient_quota" in message
                or "incorrect api key" in message
            ):
                raise

            if attempt >= max_retries:
                break

            delay = min(30.0, 2 ** (attempt - 1) + random.uniform(0.2, 1.0))
            print(
                f"⚠️ Cycle {attempt}/{max_retries} rejeté : {exc}",
                file=sys.stderr,
            )
            print(f"   Nouveau cycle dans {delay:.1f} s…", file=sys.stderr)
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def main() -> int:
    args = parse_args()

    file_path = Path(args.file).expanduser().resolve()
    charter_path = Path(args.charter).expanduser().resolve()
    lexicon_path = Path(args.lexicon).expanduser().resolve()
    log_path = Path(args.log).expanduser().resolve()

    data = load_json(file_path)
    charter = charter_path.read_text(encoding="utf-8")
    lexicon = load_json(lexicon_path)

    all_segments = collect_segments(data)
    selected = select_segments(
        all_segments,
        args.start_daf,
        args.start_segment,
        args.only_daf,
        args.force,
        args.limit,
    )

    print(f"📖 Fichier : {file_path}")
    print(f"   Premier segment ordonné : {all_segments[0].ref if all_segments else 'aucun'}")
    print(f"   Dernier segment ordonné : {all_segments[-1].ref if all_segments else 'aucun'}")
    print(f"   Segments détectés : {len(all_segments)}")
    print(f"   Segments à traiter : {len(selected)}")
    print(f"   Modèle traducteur : {args.model_translator}")
    print(f"   Modèle réviseur : {args.model_reviewer}")

    if selected:
        print(f"   Début réel : {selected[0].ref}")
        print(f"   Fin de la sélection : {selected[-1].ref}")

    if args.dry_run:
        print("\n🔍 Simulation : aucun appel API, aucune modification.")
        for i, s in enumerate(selected, 1):
            print(f"   {i}. {s.ref}")
        return 0

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY est absente. Lance : source ~/.talmudai-env")

    if not selected:
        print("\n✅ Aucun segment à traiter.")
        return 0

    if args.backup:
        backup = file_path.with_suffix(file_path.suffix + ".before-editor-v4-2.bak")
        if not backup.exists():
            shutil.copy2(file_path, backup)
            print(f"🛟 Sauvegarde créée : {backup}")
        else:
            print(f"🛟 Sauvegarde déjà présente : {backup}")

    client = OpenAI()
    translator_prompt = build_translation_prompt(charter, lexicon)
    reviewer_prompt = build_reviewer_prompt(charter, lexicon)

    grand_total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for position, segment in enumerate(selected, 1):
        print(f"\n🔎 {segment.ref}")

        try:
            result, usage = translate_and_review(
                client,
                translator_model=args.model_translator,
                reviewer_model=args.model_reviewer,
                translator_prompt=translator_prompt,
                reviewer_prompt=reviewer_prompt,
                segment=segment,
                lexicon=lexicon,
                max_retries=args.max_retries,
                max_output_tokens=args.max_output_tokens,
            )
        except KeyboardInterrupt:
            print("\n⛔ Interruption. Les segments précédents sont sauvegardés.")
            return 130
        except Exception as exc:
            append_log(
                log_path,
                {
                    "status": "error",
                    "ref": segment.ref,
                    "error": str(exc),
                    "timestamp": int(time.time()),
                },
            )
            print(f"\n❌ Échec sur {segment.ref} : {exc}", file=sys.stderr)
            return 1

        if "fr_previous" not in segment.node:
            segment.node["fr_previous"] = segment.old_fr

        review = result["review"]
        candidate = result["candidate"]

        segment.node["fr"] = review["fr_final"].strip()
        segment.node["translation_notes"] = review["incertitudes"]
        segment.node["translation_review"] = {
            "status": review["statut"],
            "corrections": review["corrections"],
            "candidate": candidate["fr_candidate"],
            "candidate_decisions": candidate["decisions_terminologiques"],
        }
        segment.node["translation_meta"] = {
            "engine": "talmud-ai-editor-v4-2",
            "translator_model": args.model_translator,
            "reviewer_model": args.model_reviewer,
            "source": "hebrew_aramaic_with_neighbor_context",
            "double_pass": True,
            "daf": segment.daf,
            "segment_id": segment.segment_id,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
            "translated_at_unix": int(time.time()),
        }

        for key in grand_total:
            grand_total[key] += usage[key]

        atomic_save(file_path, data)

        append_log(
            log_path,
            {
                "status": "ok",
                "ref": segment.ref,
                "review_status": review["statut"],
                "corrections": review["corrections"],
                "usage": usage,
                "timestamp": int(time.time()),
            },
        )

        print(
            f"✅ Sauvegardé ({position}/{len(selected)}) — "
            f"révision : {review['statut']} — "
            f"{usage['input_tokens']} entrée / {usage['output_tokens']} sortie"
        )

    print("\n✅ Traduction V4 terminée.")
    print(
        f"   Total : {grand_total['input_tokens']} entrée, "
        f"{grand_total['output_tokens']} sortie, "
        f"{grand_total['total_tokens']} tokens."
    )
    print(f"   Fichier mis à jour : {file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
