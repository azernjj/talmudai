#!/usr/bin/env python3

import json
import urllib.parse
import urllib.request
from pathlib import Path

OUTPUT = Path("public/data/mishna/bikkurim.json")
BASE = "https://www.sefaria.org/api/v3/texts/"

segments = []

for chapter in range(1, 5):
    tref = urllib.parse.quote(f"Mishnah Bikkurim {chapter}", safe="")
    url = BASE + tref

    print(f"📥 Chapitre {chapter} : {url}")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TalmudAI/1.0"}
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)

    versions = payload.get("versions", [])

    hebrew_version = next(
        (
            version for version in versions
            if version.get("language") == "he"
        ),
        None
    )

    english_version = next(
        (
            version for version in versions
            if version.get("language") == "en"
        ),
        None
    )

    if not hebrew_version:
        raise RuntimeError(
            f"Aucune version hébraïque trouvée pour le chapitre {chapter}"
        )

    he_text = hebrew_version.get("text", [])
    en_text = english_version.get("text", []) if english_version else []

    if isinstance(he_text, str):
        he_text = [he_text]

    if isinstance(en_text, str):
        en_text = [en_text]

    for index, he in enumerate(he_text, start=1):
        if not isinstance(he, str) or not he.strip():
            continue

        en = ""
        if index - 1 < len(en_text) and isinstance(en_text[index - 1], str):
            en = en_text[index - 1]

        segments.append({
            "id": f"{chapter}:{index}",
            "ref": f"Mishnah Bikkurim {chapter}:{index}",
            "he": he,
            "en": en,
            "fr": "",
            "etude_fr": {}
        })

data = {
    "title": "Mishnah Bikkurim",
    "slug": "bikkurim",
    "segments": segments
}

OUTPUT.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print(f"\n✅ {len(segments)} Michnayot enregistrées dans {OUTPUT}")
print(f"   Première : {segments[0]['ref']}")
print(f"   Dernière : {segments[-1]['ref']}")

