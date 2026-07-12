#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from openai import OpenAI

BASE_DIR = Path("public/data/parashiot")
COMMENTARY_DIR = BASE_DIR / "commentaries" / "ohr-hachaim"
INDEX_PATH = BASE_DIR / "index.json"
CACHE_PATH = Path("cache/ohr_hachaim_parashiot_translation_cache.sqlite3")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

PROMPT_SYSTEM = """Tu es un traducteur spécialisé dans les commentaires classiques de la Torah,
traduisant de l'hébreu rabbinique vers le français pour TALMUD AI.

Tu traduis le commentaire Or Ha'haïm haKadosh sur la Torah.

RÈGLES DE FIDÉLITÉ :
1. Traduis depuis l'hébreu uniquement. N'utilise pas la traduction anglaise comme base.
2. Traduis le sens exégétique, spirituel, kabbalistique et halakhique du texte.
3. Ne fais jamais une traduction littérale qui crée un contresens.
4. Ne simplifie pas les distinctions fines du commentaire.
5. Ne résume pas. Ne coupe pas les idées. Ne supprime pas les références.
6. N'ajoute pas de commentaire personnel extérieur au texte.

RÈGLES KABBALISTIQUES :
1. Conserve les notions techniques quand la traduction serait pauvre :
   Shekhina, kelipa, kelipot, sitra a'hra, sod, tikoun, nitsotsot, or, 'hochma, bina,
   middat hadin, middat harahamim, olamot, Atsilout, Beria, Yetsira, Assia.
2. Si tu traduis un terme kabbalistique, garde le terme hébreu entre parenthèses la première fois.
3. Pour קליפה, utilise généralement "écorce spirituelle (kelipa)" ou "force d'impureté", selon le contexte.
4. Pour יניקה, dans un contexte kabbalistique, traduis par "nourrissement spirituel" ou "aspiration de vitalité".
5. Pour אור, selon le contexte, traduis par "lumière", en gardant le sens spirituel.

RÈGLES HALAKHIQUES ET RABBINIQUES :
1. Ne traduis jamais un terme technique halakhique par son sens moderne banal.
2. Harmonise :
   אסור = interdit
   מותר = permis
   חייב = est tenu de / est obligé de, selon contexte
   פטור = exempt / dispensé, selon contexte
   לכתחילה = a priori
   בדיעבד = a posteriori
   ספק = doute
   קל וחומר = raisonnement a fortiori (kal va'homer)
   פשט = sens simple (pshat)
   דרש = interprétation homilétique (derash)
   רמז = allusion (remez)
   סוד = secret mystique (sod)
3. Garde les noms et termes juifs importants sous forme française/translittérée :
   Torah, mitsva, mitsvot, Chabbat, Hachem, Israël, Avraham, Yits'hak, Yaakov,
   Moché, Aharon, Cohen, Lévi, Midrash, Zohar, Tikouné HaZohar, Rambam, Ramban, Rachi.

STYLE :
1. Français clair, fidèle, fluide, adapté à une lecture d'étude.
2. Ton sobre et respectueux.
3. Garde les références bibliques et rabbiniques présentes dans le texte.
4. Si tu as un doute sérieux sur un terme ou une phrase, ajoute [?] dans la traduction.
5. Retourne uniquement la traduction française, sans Markdown, sans guillemets autour.
"""

def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def ensure_cache(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            source_hash TEXT PRIMARY KEY,
            source_text TEXT NOT NULL,
            target_text TEXT NOT NULL,
            model TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    conn.commit()

def cache_get(conn, text):
    row = conn.execute("SELECT target_text FROM translations WHERE source_hash = ?", (sha256_text(text),)).fetchone()
    return row[0] if row else None

def cache_set(conn, text, translation):
    conn.execute("""
        INSERT OR REPLACE INTO translations
        (source_hash, source_text, target_text, model, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (sha256_text(text), text, translation, MODEL, int(time.time())))
    conn.commit()

def load_json(path, fallback=None):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def get_all_parasha_slugs():
    index = load_json(INDEX_PATH, [])
    return [
        item.get("slug") or str(item.get("file", "")).replace(".json", "")
        for item in index
        if item.get("slug") or item.get("file")
    ]

def call_openai(client, hebrew_text, ref=""):
    user_content = f"""Référence : {ref}

Traduis ce passage d'Or Ha'haïm depuis l'hébreu vers le français :

{hebrew_text}
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PROMPT_SYSTEM},
            {"role": "user", "content": user_content}
        ]
    )
    return (response.choices[0].message.content or "").strip()

def translate_text(client, conn, hebrew_text, ref=""):
    hebrew_text = (hebrew_text or "").strip()
    if not hebrew_text:
        return ""

    cached = cache_get(conn, hebrew_text)
    if cached:
        return cached

    for attempt in range(1, 4):
        try:
            fr = call_openai(client, hebrew_text, ref)
            if fr:
                cache_set(conn, hebrew_text, fr)
                time.sleep(0.4)
                return fr
        except Exception as e:
            msg = str(e)
            permanent = (
                "billing_not_active" in msg or
                "invalid_api_key" in msg or
                "authentication" in msg.lower()
            )
            print(f"⚠️ Erreur OpenAI tentative {attempt}/3 : {e}")
            if permanent:
                print("❌ Erreur permanente API. Arrêt immédiat.")
                raise
            wait = attempt * 8
            print(f"   pause {wait}s...")
            time.sleep(wait)

    print("❌ Échec après 3 tentatives. Traduction laissée vide.")
    return ""

def build_output_base(src):
    return {
        "name": src.get("name", ""),
        "commentary": src.get("commentary", "Or HaChaim"),
        "range": src.get("range", ""),
        "verses": []
    }

def translate_parasha(client, conn, slug, limit=None, force=False):
    input_path = COMMENTARY_DIR / f"{slug}.json"
    output_path = COMMENTARY_DIR / f"{slug}.fr.json"

    if not input_path.exists():
        print(f"⚠️ Fichier absent, ignoré : {input_path}")
        return 0

    src = load_json(input_path, {})
    verses = src.get("verses", [])

    if not isinstance(verses, list) or not verses:
        print(f"⚠️ Aucun verset trouvé dans : {input_path}")
        return 0

    existing = load_json(output_path, build_output_base(src))
    existing_verses = existing.get("verses", []) if isinstance(existing, dict) else []
    existing_by_ref = {}
    for i, item in enumerate(existing_verses):
        if isinstance(item, dict):
            existing_by_ref[item.get("ref") or f"__index_{i}"] = item

    output = build_output_base(src)
    translated_count = 0

    print(f"\n📖 Or Ha'haïm — {slug}")
    print(f"   Entrée : {input_path}")
    print(f"   Sortie : {output_path}")
    print(f"   Modèle : {MODEL}")
    print(f"   Versets/commentaires : {len(verses)}")

    for i, verse in enumerate(verses):
        if not isinstance(verse, dict):
            output["verses"].append(verse)
            continue

        ref = verse.get("ref", "")
        key = ref or f"__index_{i}"
        old = existing_by_ref.get(key, {})
        out_verse = dict(verse)
        old_fr = (old.get("fr") or "").strip() if isinstance(old, dict) else ""

        if old_fr and not force:
            out_verse["fr"] = old_fr
            output["verses"].append(out_verse)
            continue

        he = (verse.get("he") or "").strip()
        if not he:
            out_verse["fr"] = old_fr or ""
            output["verses"].append(out_verse)
            continue

        fr = translate_text(client, conn, he, ref)
        out_verse["fr"] = fr
        output["verses"].append(out_verse)
        translated_count += 1
        print(f"✅ {slug} {ref or i + 1}")

        temp_output = build_output_base(src)
        temp_output["verses"] = output["verses"] + verses[i + 1:]
        save_json(output_path, temp_output)

        if limit and translated_count >= limit:
            print(f"⏸️ Limite atteinte : {limit}")
            return translated_count

    save_json(output_path, output)
    print(f"✅ Terminé : {output_path}")
    return translated_count

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--only", help="Slug de la paracha, ex: bereshit, noach, lekh-lekha")
    group.add_argument("--all", action="store_true", help="Traduire toutes les parachiot disponibles")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY manquant.")
        print("Exemple : source ~/.talmudai-env")
        sys.exit(1)

    if not COMMENTARY_DIR.exists():
        print(f"❌ Dossier introuvable : {COMMENTARY_DIR}")
        sys.exit(1)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH)
    ensure_cache(conn)

    client = OpenAI()
    slugs = get_all_parasha_slugs() if args.all else [args.only]

    total = 0
    for slug in slugs:
        total += translate_parasha(client, conn, slug, limit=args.limit, force=args.force)
        if args.limit and total >= args.limit:
            break

    conn.close()
    print(f"\n✅ Traduction Or Ha'haïm terminée. Nouveaux passages traduits : {total}")

if __name__ == "__main__":
    main()
