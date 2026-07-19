#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moteur V5 d'étude complète du Talmud en français.

Remplace translate-talmud-editor-v4-2.py.
Sauvegarde chaque segment, reprend automatiquement et journalise les tokens.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

VERSION = "5.0"
DEFAULT_FIELD = "etude_complete_fr"
DEFAULT_LOG = "logs/talmud_translation_v5.jsonl"

EXPERT_PROMPT = r'''
Tu es un gaon spécialiste de la Torah, de la Michna et du Talmud, ainsi qu'un
melamed d'exception. Pour UN SEUL segment, produis une étude française complète,
profonde, pédagogique et strictement fidèle à la tradition juive authentique.

FIDÉLITÉ ABSOLUE
- N'invente aucune explication, source, citation, opinion ou halakha.
- Ne présente jamais une hypothèse comme un fait.
- Distingue et attribue clairement chaque opinion.
- En cas d'incertitude écris : « À vérifier dans la source ».
- Ne donne aucune décision pratique personnelle ; indique lorsqu'un rav doit être consulté.
- Toutes les sources citées doivent être traditionnelles, identifiables et vérifiables.

TERMINOLOGIE OBLIGATOIRE
- אשמורה = « garde », jamais « veille ».
- אור lorsqu'il signifie la lumière = « or (lumière) ».
- יום טוב = « Yom Tov ».
- Conserve les termes halakhiques utiles en translittération et explique-les.

MOT À MOT
Pour chaque mot hébreu/araméen, donne uniquement son sens direct dans le contexte.
Ne réorganise pas la phrase et ne produis pas une formulation française naturelle.
Le champ sens_francais doit :
- traduire le mot lui-même, pas le sens général de la phrase ;
- conserver autant que possible temps, nombre et forme grammaticale ;
- ne pas ajouter « on » si ce sujet n'existe pas dans l'original ;
- ne pas transformer un verbe pluriel en phrase complète ;
- ne pas fusionner plusieurs mots pour rendre la traduction élégante ;
- indiquer seulement la fonction des particules sans équivalent autonome ;
- conserver le sens propre des préfixes et suffixes ;
- ne jamais devenir une paraphrase.
Exemples :
מֵאֵימָתַי = depuis quand
קוֹרִין = lisent / récitent
אֶת = marque du complément d'objet direct
שְׁמַע = Chéma
בְּעַרְבִית = au soir / dans le soir
מִשָּׁעָה = depuis le moment
שֶׁהַכֹּהֲנִים = que les prêtres
נִכְנָסִים = entrent
לֶאֱכֹל = pour manger
בִּתְרוּמָתָן = dans leur terouma / de leur terouma

CONTENU
1. texte original ; 2. traduction extrêmement fidèle ; 3. traduction fluide ;
4. explication ligne par ligne ; 5. mot à mot ; 6. mots difficiles ;
7. notions nouvelles ; 8. introduction si nécessaire ; 9. contexte général ;
10. Méfarchim classiques pertinents, désaccords et logique ; 11. halakha ;
12. conséquences pratiques ; 13. liens vers Michna, Guemara, Tanakh et sources ;
14. exemples ; 15. résumé ; 16. questions avec réponses ; 17. synthèse ;
18. sources précises.

Pour une Guemara, privilégie Rachi, Tossafot, Rif, Roch, Rambam et les autres
commentateurs réellement pertinents. Bartenoura, Tossafot Yom Tov et Tiféret
Israël ne doivent apparaître que lorsqu'une Michna est directement étudiée.
Ne remplis jamais artificiellement la liste des auteurs.

Réponds uniquement avec un objet JSON valide conforme au schéma demandé.
'''

REVIEWER_PROMPT = r'''
Tu es le vérificateur final d'une édition française traditionnelle du Talmud.
Corrige entièrement l'étude reçue. Vérifie la fidélité au texte, la grammaire,
le mot à mot brut dans l'ordre, les attributions, les désaccords, les références,
la prudence halakhique, l'absence d'invention et les règles : אשמורה = garde,
אור = or (lumière), יום טוב = Yom Tov. Supprime ce qui n'est pas vérifiable ou
marque « À vérifier dans la source ». Retourne uniquement le JSON final corrigé.
'''

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reference", "texte_original", "traduction_fidele", "traduction_fluide",
        "explication_ligne_par_ligne", "mot_a_mot", "mots_difficiles",
        "notions_nouvelles", "introduction", "contexte_general", "mefarshim",
        "halakha", "consequences_pratiques", "liens_sources", "exemples_concrets",
        "resume", "questions_revision", "synthese_finale", "sources", "avertissements"
    ],
    "properties": {
        "reference": {"type": "string"},
        "texte_original": {"type": "string"},
        "traduction_fidele": {"type": "string"},
        "traduction_fluide": {"type": "string"},
        "explication_ligne_par_ligne": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["texte", "traduction", "explication"],
            "properties": {"texte": {"type": "string"}, "traduction": {"type": "string"}, "explication": {"type": "string"}}
        }},
        "mot_a_mot": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["mot_hebreu", "translitteration", "sens_francais", "fonction_grammaticale", "note"],
            "properties": {
                "mot_hebreu": {"type": "string"}, "translitteration": {"type": "string"},
                "sens_francais": {"type": "string"}, "fonction_grammaticale": {"type": "string"}, "note": {"type": "string"}
            }
        }},
        "mots_difficiles": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["terme", "definition", "role_dans_le_passage"],
            "properties": {"terme": {"type": "string"}, "definition": {"type": "string"}, "role_dans_le_passage": {"type": "string"}}
        }},
        "notions_nouvelles": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["notion", "explication"],
            "properties": {"notion": {"type": "string"}, "explication": {"type": "string"}}
        }},
        "introduction": {"type": "string"},
        "contexte_general": {"type": "string"},
        "mefarshim": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["auteur", "reference", "opinion", "logique", "desaccords", "niveau_certitude"],
            "properties": {
                "auteur": {"type": "string"}, "reference": {"type": "string"}, "opinion": {"type": "string"},
                "logique": {"type": "string"}, "desaccords": {"type": "string"},
                "niveau_certitude": {"type": "string", "enum": ["certain", "probable", "a_verifier"]}
            }
        }},
        "halakha": {"type": "object", "additionalProperties": False,
            "required": ["decision", "sources", "reserve"],
            "properties": {"decision": {"type": "string"}, "sources": {"type": "array", "items": {"type": "string"}}, "reserve": {"type": "string"}}
        },
        "consequences_pratiques": {"type": "array", "items": {"type": "string"}},
        "liens_sources": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["type", "reference", "lien_explique"],
            "properties": {"type": {"type": "string"}, "reference": {"type": "string"}, "lien_explique": {"type": "string"}}
        }},
        "exemples_concrets": {"type": "array", "items": {"type": "string"}},
        "resume": {"type": "array", "items": {"type": "string"}},
        "questions_revision": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["question", "reponse"],
            "properties": {"question": {"type": "string"}, "reponse": {"type": "string"}}
        }},
        "synthese_finale": {"type": "string"},
        "sources": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["auteur_ou_ouvrage", "reference", "usage", "statut"],
            "properties": {
                "auteur_ou_ouvrage": {"type": "string"}, "reference": {"type": "string"}, "usage": {"type": "string"},
                "statut": {"type": "string", "enum": ["verifie", "a_verifier"]}
            }
        }},
        "avertissements": {"type": "array", "items": {"type": "string"}}
    }
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def append_log(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.stem}.before-v5-{stamp}{path.suffix}.bak")
    shutil.copy2(path, dest)
    return dest


def daf_key(value: str) -> tuple[int, int, str]:
    m = re.fullmatch(r"\s*(\d+)\s*([abAB])?\s*", str(value))
    return (int(m.group(1)), 0 if (m.group(2) or "a").lower() == "a" else 1, value) if m else (10**9, 0, value)


def get_dapim(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        for key in ("dapim", "pages", "dafim"):
            if isinstance(data.get(key), dict):
                return data[key]
        for value in data.values():
            try:
                return get_dapim(value)
            except LookupError:
                pass
    raise LookupError("Clé dapim/pages/dafim introuvable.")


def get_segments(page: Any) -> list[dict[str, Any]]:
    if isinstance(page, list) and all(isinstance(x, dict) for x in page):
        return page
    if isinstance(page, dict):
        for key in ("segments", "items", "texts"):
            value = page.get(key)
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return value
    raise LookupError("Liste de segments introuvable.")


def original_text(segment: dict[str, Any]) -> str:
    for key in ("he", "hebrew", "text_he", "original", "text", "source", "heb"):
        value = segment.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError("Texte hébreu/araméen introuvable dans le segment.")


def tractate_name(path: Path, data: Any) -> str:
    if isinstance(data, dict):
        for key in ("title", "masekhet", "tractate", "name", "slug"):
            if isinstance(data.get(key), str) and data[key].strip():
                return data[key].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def complete(segment: dict[str, Any], field: str) -> bool:
    value = segment.get(field)
    return isinstance(value, dict) and bool(value.get("traduction_fidele")) and bool(value.get("synthese_finale")) and isinstance(value.get("sources"), list)


def output_text(response: Any) -> str:
    direct = getattr(response, "output_text", None)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    pieces: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                pieces.append(text)
            elif getattr(text, "value", None):
                pieces.append(text.value)
    return "\n".join(pieces).strip()


def parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        result = json.loads(text[start:end + 1])
    if not isinstance(result, dict):
        raise ValueError("La réponse doit être un objet JSON.")
    return result


def usage(response: Any) -> dict[str, int]:
    u = getattr(response, "usage", None)
    def read(*names: str) -> int:
        for name in names:
            value = getattr(u, name, None) if u is not None else None
            if isinstance(value, int):
                return value
            if isinstance(u, dict) and isinstance(u.get(name), int):
                return u[name]
        return 0
    inp, out = read("input_tokens", "prompt_tokens"), read("output_tokens", "completion_tokens")
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": read("total_tokens") or inp + out}


def call_model(client: OpenAI, model: str, system: str, user: str, max_tokens: int,
               effort: str, retries: int) -> tuple[dict[str, Any], dict[str, int]]:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            params: dict[str, Any] = {
                "model": model,
                "input": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_output_tokens": max_tokens,
            }
            if effort != "none":
                params["reasoning"] = {"effort": effort}
            try:
                response = client.responses.create(**params, text={"format": {
                    "type": "json_schema", "name": "talmud_study", "strict": True, "schema": SCHEMA
                }})
            except Exception as structured_error:
                msg = str(structured_error).lower()
                if not any(x in msg for x in ("json_schema", "text.format", "unknown parameter", "unsupported", "invalid_request")):
                    raise
                response = client.responses.create(**params)
            raw = output_text(response)
            if not raw:
                raise RuntimeError(f"Réponse vide : status={getattr(response, 'status', None)!r}, incomplete={getattr(response, 'incomplete_details', None)!r}")
            return parse_json(raw), usage(response)
        except Exception as exc:
            last = exc
            if attempt == retries:
                break
            delay = min(30, 2 ** attempt)
            print(f"⚠️ Échec API {attempt}/{retries}: {exc}; nouvel essai dans {delay}s", file=sys.stderr)
            time.sleep(delay)
    assert last is not None
    raise last


def ensure_final(study: dict[str, Any], reference: str, original: str) -> list[str]:
    warnings: list[str] = []
    study["reference"] = reference
    study["texte_original"] = original
    for key in ("traduction_fidele", "traduction_fluide", "contexte_general", "synthese_finale"):
        if not isinstance(study.get(key), str) or not study[key].strip():
            warnings.append(f"Champ vide : {key}")
    for key in ("mot_a_mot", "mefarshim", "sources", "questions_revision"):
        if not isinstance(study.get(key), list):
            warnings.append(f"Champ non conforme : {key}")
            study[key] = []
    study.setdefault("avertissements", [])
    for warning in warnings:
        if warning not in study["avertissements"]:
            study["avertissements"].append(warning)
    return warnings


def prompt_expert(reference: str, original: str, before: str, after: str) -> str:
    return f'''RÉFÉRENCE\n{reference}\n\nTEXTE ORIGINAL\n{original}\n\nCONTEXTE AVANT\n{before or "Non fourni."}\n\nCONTEXTE APRÈS\n{after or "Non fourni."}\n\nLe contexte sert seulement à comprendre l'enchaînement. Produis l'étude du segment seul.\nSCHÉMA JSON STRICT\n{json.dumps(SCHEMA, ensure_ascii=False)}\nRetourne seulement le JSON.'''


def prompt_reviewer(reference: str, original: str, draft: dict[str, Any]) -> str:
    return f'''RÉFÉRENCE\n{reference}\n\nTEXTE ORIGINAL\n{original}\n\nÉTUDE À CORRIGER\n{json.dumps(draft, ensure_ascii=False)}\n\nSCHÉMA JSON STRICT\n{json.dumps(SCHEMA, ensure_ascii=False)}\nRetourne seulement le JSON final corrigé.'''


def arguments() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Étude complète du Talmud en français — moteur V5")
    p.add_argument("--file", required=True)
    p.add_argument("--only-daf")
    p.add_argument("--start-segment", type=int, default=1)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--model-translator", default="gpt-5.5")
    p.add_argument("--model-reviewer", default="gpt-5.5")
    p.add_argument("--max-output-tokens", type=int, default=12000)
    p.add_argument("--reasoning-effort", choices=("none", "low", "medium", "high"), default="low")
    p.add_argument("--field", default=DEFAULT_FIELD)
    p.add_argument("--force", action="store_true")
    p.add_argument("--backup", action="store_true")
    p.add_argument("--skip-review", action="store_true", help="Un seul appel API, moins cher")
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--log", default=DEFAULT_LOG)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = arguments()
    path, log = Path(args.file), Path(args.log)
    if not path.is_file():
        print(f"❌ Fichier introuvable : {path}", file=sys.stderr); return 2
    if args.start_segment < 1 or args.retries < 1:
        print("❌ Paramètre numérique invalide.", file=sys.stderr); return 2

    data = load_json(path)
    dapim = get_dapim(data)
    masekhet = tractate_name(path, data)
    if args.backup and not args.dry_run:
        print(f"🛟 Sauvegarde : {backup(path)}")

    chosen: list[tuple[str, int, dict[str, Any], list[dict[str, Any]]]] = []
    for daf in sorted(dapim, key=daf_key):
        if args.only_daf and daf != args.only_daf:
            continue
        segs = get_segments(dapim[daf])
        for i, seg in enumerate(segs):
            if args.only_daf and i + 1 < args.start_segment:
                continue
            if not args.force and complete(seg, args.field):
                continue
            chosen.append((daf, i, seg, segs))
            if args.limit and len(chosen) >= args.limit:
                break
        if args.limit and len(chosen) >= args.limit:
            break

    print(f"📖 Fichier : {path}\n   Traité : {masekhet}\n   Segments à traiter : {len(chosen)}")
    print(f"   Expert : {args.model_translator}\n   Révision : {'désactivée' if args.skip_review else args.model_reviewer}")
    if args.dry_run:
        for daf, i, *_ in chosen: print(f"- {masekhet} {daf}:{i+1}")
        return 0
    if not chosen:
        print("✅ Aucun segment à traiter."); return 0
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY n'est pas définie.", file=sys.stderr); return 2

    client = OpenAI()
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    ok = failed = 0
    for position, (daf, index, segment, segments) in enumerate(chosen, 1):
        reference = f"{masekhet} {daf}:{index+1}"
        print(f"\n🔎 {reference} ({position}/{len(chosen)})")
        try:
            original = original_text(segment)
            before = original_text(segments[index-1]) if index > 0 else ""
            after = original_text(segments[index+1]) if index + 1 < len(segments) else ""
            draft, use1 = call_model(client, args.model_translator, EXPERT_PROMPT,
                                     prompt_expert(reference, original, before, after),
                                     args.max_output_tokens, args.reasoning_effort, args.retries)
            ensure_final(draft, reference, original)
            if args.skip_review:
                final, use2 = draft, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            else:
                final, use2 = call_model(client, args.model_reviewer, REVIEWER_PROMPT,
                                         prompt_reviewer(reference, original, draft),
                                         args.max_output_tokens, args.reasoning_effort, args.retries)
                ensure_final(final, reference, original)

            total = {k: use1[k] + use2[k] for k in totals}
            for k in totals: totals[k] += total[k]
            segment[args.field] = final
            segment["fr"] = final["traduction_fidele"]
            segment["fr_fluide"] = final["traduction_fluide"]
            segment["translation_meta_v5"] = {
                "script_version": VERSION, "translated_at": now(),
                "model_translator": args.model_translator,
                "model_reviewer": None if args.skip_review else args.model_reviewer,
                "usage": {"translator": use1, "reviewer": use2, "total": total}
            }
            save_json(path, data)
            append_log(log, {"timestamp": now(), "status": "success", "file": str(path),
                             "reference": reference, "usage": total})
            ok += 1
            print(f"✅ Sauvegardé — {total['input_tokens']} entrée, {total['output_tokens']} sortie, {total['total_tokens']} total")
        except KeyboardInterrupt:
            print("\n🛑 Arrêt demandé. Tout ce qui était terminé est sauvegardé.")
            break
        except Exception as exc:
            failed += 1
            print(f"❌ {reference} : {exc}", file=sys.stderr)
            append_log(log, {"timestamp": now(), "status": "error", "file": str(path),
                             "reference": reference, "error": str(exc), "traceback": traceback.format_exc()})

    print("\n" + "=" * 60)
    print(f"✅ Réussites : {ok}\n❌ Échecs : {failed}")
    print(f"📥 Entrée : {totals['input_tokens']}\n📤 Sortie : {totals['output_tokens']}\n🧮 Total : {totals['total_tokens']}")
    print(f"💾 Fichier : {path}\n📝 Journal : {log}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
