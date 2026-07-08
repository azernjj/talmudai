#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TALMUD AI - Traducteur halakhique hébreu -> français par SIMAN.

Installation :
  source .venv/bin/activate
  pip install openai

Variables :
  export OPENAI_API_KEY="sk-..."
  export OPENAI_MODEL="gpt-5.5"

Tests :
  python3 scripts/translate-shulchan-arukh-by-siman-openai.py --only yore-dea --siman 1
  python3 scripts/translate-shulchan-arukh-by-siman-openai.py --only yore-dea --from-siman 1 --to-siman 3

Traduction complète :
  python3 scripts/translate-shulchan-arukh-by-siman-openai.py --only yore-dea
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path("public/data/shulchan-arukh")
CACHE_PATH = Path("cache/halakhic_siman_translation_cache.sqlite3")

DEFAULT_FILES = [
    "orach-chaim",
    "yore-dea",
    "even-haezer",
    "hoshen-mishpat",
]

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

PROMPT_SYSTEM = """Tu es un traducteur spécialisé en textes halakhiques classiques, traduisant de l'hébreu vers le français pour TALMUD AI.

Tu traduis le Choulhan Aroukh.

RÈGLES STRICTES :
1. Tu dois traduire le sens juridique halakhique, pas une traduction littérale mot-à-mot.
2. Ne traduis jamais un terme technique halakhique par son sens moderne banal.
3. En cas de doute sur un terme technique, ajoute [?] dans la traduction, mais n'invente pas.
4. Ne simplifie jamais les distinctions juridiques fines : interdit/permis, obligation/exemption, aveu/témoignage, amende/dommage monétaire, a priori/a posteriori.
5. Garde les termes techniques intraduisibles en translittération française lorsque c'est préférable : Chabbat, Yom Tov, guet, ketouba, mikvé, she'hita, kashrout, Cohen, Lévi, Israël, non-Juif.
6. Harmonise toujours :
   אסור = interdit
   מותר = permis
   חייב = est tenu de / est obligé de selon contexte
   פטור = est dispensé / exempt selon contexte
   לכתחילה = a priori
   בדיעבד = a posteriori
   ספק = doute
   מחמיר = rigoureux / adopte une position stricte
   מקיל = indulgent / adopte une position permissive
7. N'ajoute pas de commentaire explicatif extérieur au texte.
8. Respecte exactement les numéros de se'ifim donnés.
9. Tu dois répondre UNIQUEMENT en JSON valide, sans Markdown, sans texte autour.

Format obligatoire :
{
  "siman": 1,
  "seifim": [
    {"seif": 1, "fr": "..."},
    {"seif": 2, "fr": "..."}
  ]
}
"""

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_cache(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS siman_translations (
            source_hash TEXT PRIMARY KEY,
            slug TEXT NOT NULL,
            siman INTEGER NOT NULL,
            source_json TEXT NOT NULL,
            target_json TEXT NOT NULL,
            model TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()


def load_json(path: Path, fallback=None):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_empty_fr(src, input_path):
    return {
        "slug": src.get("slug", ""),
        "title": src.get("title", ""),
        "heTitle": src.get("heTitle", ""),
        "source": "OpenAI halakhic Hebrew-to-French translation by siman",
        "sourceFile": str(input_path),
        "model": MODEL,
        "simanim": []
    }


def siman_payload(siman):
    return {
        "siman": siman.get("siman"),
        "seifim": [
            {"seif": seif.get("seif"), "he": seif.get("he", "")}
            for seif in siman.get("seifim", [])
            if (seif.get("he") or "").strip()
        ]
    }


def cache_get(conn, payload):
    source_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    row = conn.execute(
        "SELECT target_json FROM siman_translations WHERE source_hash = ?",
        (sha256_text(source_json),)
    ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def cache_set(conn, slug, siman_number, payload, result):
    source_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    target_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
    conn.execute(
        """
        INSERT OR REPLACE INTO siman_translations
        (source_hash, slug, siman, source_json, target_json, model, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sha256_text(source_json),
            slug,
            int(siman_number),
            source_json,
            target_json,
            MODEL,
            int(time.time())
        )
    )
    conn.commit()


def extract_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError("Réponse OpenAI non JSON.")


def normalize_result(result, source_payload):
    if not isinstance(result, dict):
        raise ValueError("Le résultat n'est pas un objet JSON.")

    source_siman = int(source_payload["siman"])
    result["siman"] = source_siman

    source_ids = [int(x["seif"]) for x in source_payload.get("seifim", [])]
    received = {}

    for item in result.get("seifim", []):
        try:
            n = int(item.get("seif"))
        except Exception:
            continue
        received[n] = {"seif": n, "fr": str(item.get("fr", "")).strip()}

    normalized = []
    missing = []

    for n in source_ids:
        if n in received and received[n]["fr"]:
            normalized.append(received[n])
        else:
            missing.append(n)
            normalized.append({"seif": n, "fr": ""})

    if missing:
        raise ValueError(f"Se'ifim manquants ou vides : {missing}")

    return {"siman": source_siman, "seifim": normalized}


def call_openai(client, payload):
    user_content = (
        "Traduis le siman suivant du Choulhan Aroukh de l'hébreu vers le français.\n"
        "Réponds uniquement en JSON valide selon le format demandé.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    
    response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": PROMPT_SYSTEM},
        {"role": "user", "content": user_content}
    ]
)
    return response.choices[0].message.content or ""


def translate_siman(client, conn, slug, siman):
    payload = siman_payload(siman)

    if not payload["seifim"]:
        return {"siman": siman.get("siman"), "title": siman.get("title", ""), "seifim": []}

    cached = cache_get(conn, payload)
    if cached:
        return {"siman": siman.get("siman"), "title": siman.get("title", ""), "seifim": cached["seifim"]}

    he_chars = sum(len(x.get("he", "")) for x in payload["seifim"])
    if he_chars > 18000:
        print(f"⚠️ Siman {siman.get('siman')} très long ({he_chars} caractères).")

    for attempt in range(1, 4):
        try:
            raw = call_openai(client, payload)
            parsed = extract_json(raw)
            normalized = normalize_result(parsed, payload)
            cache_set(conn, slug, siman.get("siman"), payload, normalized)
            time.sleep(0.5)
            return {"siman": siman.get("siman"), "title": siman.get("title", ""), "seifim": normalized["seifim"]}
        except Exception as e:
            msg = str(e)
            permanent = (
                "billing_not_active" in msg or
                "invalid_api_key" in msg or
                "authentication" in msg.lower()
            )
            print(f"⚠️ Erreur siman {siman.get('siman')} tentative {attempt}/3 : {e}")
            if permanent:
                print("❌ Erreur permanente API. Arrêt immédiat.")
                raise
            wait = attempt * 8
            print(f"   pause {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Échec traduction siman {siman.get('siman')} après 3 tentatives.")


def find_existing_siman(fr, siman_number):
    for s in fr.get("simanim", []):
        if str(s.get("siman")) == str(siman_number):
            return s
    return None


def translate_file(client, conn, slug, only_siman=None, from_siman=None, to_siman=None, force=False):
    input_path = BASE_DIR / f"{slug}.json"
    output_path = BASE_DIR / f"{slug}.fr.json"

    if not input_path.exists():
        print(f"❌ Fichier introuvable : {input_path}")
        return

    src = load_json(input_path)
    fr = load_json(output_path, make_empty_fr(src, input_path))

    print(f"\n📘 Traduction par siman : {slug}")
    print(f"   Entrée : {input_path}")
    print(f"   Sortie : {output_path}")
    print(f"   Modèle : {MODEL}")

    for siman in src.get("simanim", []):
        n = int(siman.get("siman", 0))

        if only_siman and n != only_siman:
            continue
        if from_siman and n < from_siman:
            continue
        if to_siman and n > to_siman:
            continue

        existing = find_existing_siman(fr, n)
        if existing and existing.get("seifim") and not force:
            print(f"↩️ {slug} siman {n} déjà traduit, ignoré.")
            continue

        translated = translate_siman(client, conn, slug, siman)

        fr["simanim"] = [s for s in fr.get("simanim", []) if str(s.get("siman")) != str(n)]
        fr["simanim"].append(translated)
        fr["simanim"].sort(key=lambda x: int(x.get("siman", 0)))

        save_json(output_path, fr)
        print(f"✅ {slug} siman {n} sauvegardé ({len(translated.get('seifim', []))} se'ifim)")

    print(f"✅ Terminé : {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=DEFAULT_FILES, required=True)
    parser.add_argument("--siman", type=int, default=None, help="Traduire seulement ce siman.")
    parser.add_argument("--from-siman", type=int, default=None)
    parser.add_argument("--to-siman", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Retraduire même si le siman existe déjà.")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY manquant.")
        print('Exemple : export OPENAI_API_KEY="sk-..."')
        sys.exit(1)

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH)
    ensure_cache(conn)

    client = OpenAI()

    translate_file(
        client=client,
        conn=conn,
        slug=args.only,
        only_siman=args.siman,
        from_siman=args.from_siman,
        to_siman=args.to_siman,
        force=args.force
    )

    conn.close()
    print("\n✅ Traduction terminée.")


if __name__ == "__main__":
    main()
