#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TALMUD AI — Traduction légère de la Michna avec OpenAI Responses API.

Le script :
- lit un fichier JSON de Michna ;
- traduit directement depuis l'hébreu ;
- ajoute les Méfarchim en français ;
- sauvegarde après chaque Michna ;
- reprend automatiquement sans --force.

Exemple :
    python3 scripts/translate-mishna-direct-openai-V2.py \
      --file public/data/mishna/peah.json \
      --limit 1 \
      --model gpt-5.5 \
      --force \
      --backup
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from openai import OpenAI


DEFAULT_MODEL = "gpt-5.5"

SYSTEM_PROMPT = """Tu es un Rav, talmid hakham et spécialiste de la Michna, de l'hébreu rabbinique et des commentaires classiques.

Ta mission est de produire une traduction française de très haute qualité, directement à partir du texte hébreu de la Michna, sans utiliser la traduction anglaise comme source.

RÈGLES

- Traduis uniquement depuis le texte hébreu.
- La traduction doit être fidèle, précise, naturelle et élégante.
- Ne résume jamais le texte.
- N'ajoute aucune explication dans la traduction.
- Respecte la terminologie traditionnelle.

Conserver les termes suivants lorsqu'ils apparaissent :

- Chabbat
- Yom Tov
- Michna
- Guemara
- halakha
- mitsva
- terouma
- maasser
- peah
- Chemita
- Cohen
- Lévi

RÈGLES IMPORTANTES

- יום טוב = Yom Tov (jamais festival, fête ou jour bon)
- הָאַשְׁמוּרָה = la garde
- אַשְׁמוּרָה = une garde
- אוֹר doit être traduit selon le contexte (lumière, clarté, lever du jour) et jamais par « ou ».
- Ne jamais translittérer un mot hébreu lorsqu'une traduction française correcte existe.

MÉFARCHIM

Après la traduction, présente obligatoirement entre 2 et 5 Méfarchim permettant de comprendre cette Michna.

Privilégie :

1. Rabbénou Ovadia de Bartenoura
2. Rambam (Commentaire sur la Michna)
3. Tossafot Yom Tov
4. Tiféret Israël
5. Rachi lorsque son commentaire sur la Guemara éclaire directement cette Michna.
6. Tossafot lorsque leur commentaire sur la Guemara éclaire directement cette Michna.

Présente au minimum deux commentaires classiques réellement utiles. Privilégie Bartenoura et le Rambam lorsqu’ils éclairent cette Michna, puis Tossafot Yom Tov et Tiféret Israël.

Chaque commentaire doit être rédigé en français, très clair et fidèle.

FORMAT DE SORTIE

Retourne uniquement le JSON suivant :

{
  "traduction_fr": "...",
  "mefarshim": [
    {
      "auteur": "...",
      "reference": "...",
      "explication": "..."
    }
  ]
}

Aucun texte avant ou après le JSON.
Aucune autre section."""


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "traduction_fr": {"type": "string"},
        "mefarshim": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "auteur": {"type": "string"},
                    "reference": {"type": "string"},
                    "explication": {"type": "string"},
                },
                "required": ["auteur", "reference", "explication"],
            },
        },
    },
    "required": ["traduction_fr", "mefarshim"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Traduit un fichier de Michna avec OpenAI."
    )
    parser.add_argument("--file", required=True, help="Fichier JSON de Michna.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--max-output-tokens", type=int, default=4000)
    return parser.parse_args()


def find_mishnayot(value: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            hebrew = item.get("he")
            if isinstance(hebrew, str) and hebrew.strip():
                results.append(item)
                return

            for child in item.values():
                walk(child)

        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return results


def get_existing_mefarshim(mishnah: dict[str, Any]) -> list[Any] | None:
    """
    etude_fr peut être un dictionnaire, None, une chaîne ou une ancienne structure.
    Cette fonction évite l'AttributeError rencontré précédemment.
    """
    etude_fr = mishnah.get("etude_fr")

    if not isinstance(etude_fr, dict):
        return None

    mefarshim = etude_fr.get("mefarshim")
    return mefarshim if isinstance(mefarshim, list) else None


def translate_mishnah(
    client: OpenAI,
    model: str,
    reference: str,
    hebrew: str,
    max_output_tokens: int,
) -> tuple[dict[str, Any], dict[str, int]]:
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"RÉFÉRENCE : {reference}\n\n"
                    f"TEXTE HÉBREU DE LA MICHNA :\n{hebrew}"
                ),
            },
        ],
        max_output_tokens=max_output_tokens,
        text={
            "format": {
                "type": "json_schema",
                "name": "traduction_michna_fr",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            }
        },
    )

    raw = (response.output_text or "").strip()
    if not raw:
        raise RuntimeError("OpenAI a renvoyé une réponse vide.")

    result = json.loads(raw)

    translation = str(result.get("traduction_fr", "")).strip()
    if not translation:
        raise RuntimeError("Le champ traduction_fr est vide.")

    mefarshim = result.get("mefarshim")
    if not isinstance(mefarshim, list):
        raise RuntimeError("Le champ mefarshim n'est pas une liste.")

    api_usage = getattr(response, "usage", None)
    usage = {
        "input_tokens": int(getattr(api_usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(api_usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(api_usage, "total_tokens", 0) or 0),
    }

    return result, usage


def main() -> int:
    args = parse_args()

    if args.start < 1:
        raise SystemExit("--start doit être supérieur ou égal à 1.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit(
            "❌ OPENAI_API_KEY manquante. Lance : source ~/.talmudai-env"
        )

    path = Path(args.file).expanduser()
    if not path.exists():
        raise SystemExit(f"❌ Fichier introuvable : {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"❌ JSON invalide, ligne {exc.lineno}, colonne {exc.colno} : {exc.msg}"
        ) from exc

    mishnayot = find_mishnayot(data)
    selected = mishnayot[args.start - 1 :]

    if not args.force:
        selected = [
            mishnah
            for mishnah in selected
            if not str(mishnah.get("fr", "")).strip()
            or not get_existing_mefarshim(mishnah)
        ]

    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit doit être supérieur ou égal à 1.")
        selected = selected[: args.limit]

    print(f"📖 Fichier : {path.resolve()}")
    print(f"   Modèle : {args.model}")
    print(f"   Michnayot détectées : {len(mishnayot)}")
    print(f"   Michnayot à traiter : {len(selected)}")
    print(f"   Mode forcé : {'oui' if args.force else 'non'}")

    if args.backup:
        backup = path.with_suffix(path.suffix + ".before-openai-v2.bak")
        shutil.copy2(path, backup)
        print(f"🛟 Sauvegarde : {backup.resolve()}")

    if not selected:
        print("\n✅ Aucune Michna à traiter.")
        return 0

    client = OpenAI(api_key=api_key)

    total_input = 0
    total_output = 0
    total_tokens = 0

    for position, mishnah in enumerate(selected, start=1):
        reference = str(
            mishnah.get("ref")
            or mishnah.get("id")
            or f"Michna {args.start + position - 1}"
        )
        hebrew = str(mishnah["he"]).strip()

        print(f"\n🔎 {reference}")

        try:
            result, usage = translate_mishnah(
                client=client,
                model=args.model,
                reference=reference,
                hebrew=hebrew,
                max_output_tokens=args.max_output_tokens,
            )
        except KeyboardInterrupt:
            print("\n⛔ Interruption. Les Michnayot précédentes sont conservées.")
            return 130
        except Exception as exc:
            print(f"❌ Échec sur {reference} : {exc}")
            return 1

        translation = result["traduction_fr"].strip()

        mishnah["fr"] = translation
        mishnah["etude_fr"] = {
            "traduction_fr": translation,
            "mefarshim": result["mefarshim"],
        }

        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        total_input += usage["input_tokens"]
        total_output += usage["output_tokens"]
        total_tokens += usage["total_tokens"]

        print(
            f"✅ Sauvegardé ({position}/{len(selected)}) — "
            f"{usage['input_tokens']} entrée / "
            f"{usage['output_tokens']} sortie"
        )

    print(
        f"\n✅ Terminé. Tokens : {total_input} entrée, "
        f"{total_output} sortie, {total_tokens} total"
    )
    print(f"   Fichier mis à jour : {path.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
