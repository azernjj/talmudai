#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import shutil
from pathlib import Path
from openai import OpenAI

PROMPT = """Tu es un Rav, talmid hakham et spécialiste de la Michna, de l'hébreu rabbinique et des commentaires classiques.

Traduis la Michna directement depuis l'hébreu, sans utiliser l'anglais.
La traduction doit être fidèle, complète, naturelle et élégante.
N'ajoute aucune explication dans la traduction.

Conserve la terminologie traditionnelle : Chabbat, Yom Tov, Michna, Guemara,
halakha, mitsva, terouma, maasser, peah, Chemita, Cohen, Lévi.

Règles :
- יום טוב = Yom Tov, jamais festival, fête ou jour bon.
- הָאַשְׁמוּרָה = la garde.
- אַשְׁמוּרָה = une garde.
- אוֹר = lumière, clarté ou lever du jour selon le contexte, jamais « ou ».

Après la traduction, donne obligatoirement entre 2 et 5 Méfarchim en français.
Présente en priorité :
1. Rabbénou Ovadia de Bartenoura
2. Rambam, Commentaire sur la Michna
3. Tossafot Yom Tov
4. Tiféret Israël
5. Rachi ou Tossafot seulement si la Guemara correspondante éclaire directement cette Michna

Pour chaque Méfaresh, donne son nom, une référence précise et une explication claire.
N'invente jamais une opinion. Si une référence exacte n'est pas certaine, écris
« référence générale sur cette Michna » plutôt qu'une fausse référence.

Retourne uniquement le JSON demandé."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "traduction_fr": {"type": "string"},
        "mefarshim": {
            "type": "array",
            "minItems": 2,
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

def trouver(obj):
    resultat = []
    if isinstance(obj, dict):
        if isinstance(obj.get("he"), str) and obj["he"].strip():
            resultat.append(obj)
        else:
            for valeur in obj.values():
                resultat.extend(trouver(valeur))
    elif isinstance(obj, list):
        for valeur in obj:
            resultat.extend(trouver(valeur))
    return resultat

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True)
    p.add_argument("--model", default="gpt-5.5")
    p.add_argument("--limit", type=int)
    p.add_argument("--force", action="store_true")
    p.add_argument("--backup", action="store_true")
    args = p.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY manquante. Lance : source ~/.talmudai-env")

    chemin = Path(args.file)
    data = json.loads(chemin.read_text(encoding="utf-8"))
    toutes = trouver(data)

    a_traiter = []
    for m in toutes:
        etude = m.get("etude_fr")
        mefarshim = etude.get("mefarshim") if isinstance(etude, dict) else None
        if args.force or not str(m.get("fr", "")).strip() or not mefarshim:
            a_traiter.append(m)

    if args.limit:
        a_traiter = a_traiter[:args.limit]

    print(f"📖 Fichier : {chemin.resolve()}")
    print(f"   Modèle : {args.model}")
    print(f"   Michnayot détectées : {len(toutes)}")
    print(f"   Michnayot à traiter : {len(a_traiter)}")

    if args.backup:
        backup = chemin.with_suffix(chemin.suffix + ".bak")
        shutil.copy2(chemin, backup)
        print(f"🛟 Sauvegarde : {backup.resolve()}")

    client = OpenAI()
    input_total = output_total = 0

    for i, m in enumerate(a_traiter, 1):
        ref = str(m.get("ref") or m.get("id") or i)
        print(f"\n🔎 {ref}")

        r = client.responses.create(
            model=args.model,
            input=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": f"Référence : {ref}\n\nTexte hébreu :\n{m['he']}"},
            ],
            max_output_tokens=3000,
            text={"format": {
                "type": "json_schema",
                "name": "mishna_fr",
                "strict": True,
                "schema": SCHEMA,
            }},
        )

        resultat = json.loads(r.output_text)
        traduction = resultat["traduction_fr"].strip()

        m["fr"] = traduction
        m["etude_fr"] = {
            "traduction_fr": traduction,
            "mefarshim": resultat["mefarshim"],
        }

        chemin.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        entree = int(getattr(r.usage, "input_tokens", 0) or 0)
        sortie = int(getattr(r.usage, "output_tokens", 0) or 0)
        input_total += entree
        output_total += sortie
        print(f"✅ Sauvegardé ({i}/{len(a_traiter)}) — {entree} entrée / {sortie} sortie")

    print(f"\n✅ Terminé — {input_total} entrée / {output_total} sortie")

if __name__ == "__main__":
    main()
