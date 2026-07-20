#!/usr/bin/env python3
import json
import re
from pathlib import Path


DATA_DIR = Path("public/data/merged")


def daf_key(daf):
    match = re.fullmatch(r"(\d+)([abAB])", str(daf).strip())
    if not match:
        return (999999, 9)
    number = int(match.group(1))
    side = 0 if match.group(2).lower() == "a" else 1
    return (number, side)


def get_segments(daf_data):
    if isinstance(daf_data, dict):
        segments = daf_data.get("segments", [])
        return segments if isinstance(segments, list) else []
    if isinstance(daf_data, list):
        return daf_data
    return []


def is_shabbat(filename, data):
    names = [
        filename,
        str(data.get("title", "")),
        str(data.get("name", "")),
        str(data.get("masekhet", "")),
        str(data.get("tractate", "")),
    ]
    text = " ".join(names).lower()
    return "shabbat" in text or "chabbat" in text or "שבת" in text


def main():
    if not DATA_DIR.exists():
        print(f"❌ Dossier introuvable : {DATA_DIR}")
        return

    total_remaining = 0
    shabbat_remaining = 0
    other_remaining = 0
    files_count = 0

    print("Comptage des segments restant à traiter")
    print("Shabbat 2a à 8b est exclu.")
    print("-" * 60)

    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except Exception as error:
            print(f"⚠️ Impossible de lire {path.name} : {error}")
            continue

        if not isinstance(data, dict):
            continue

        dapim = data.get("dapim", {})
        if not isinstance(dapim, dict):
            continue

        files_count += 1
        tractate_total = 0
        shabbat = is_shabbat(path.stem, data)

        for daf, daf_data in dapim.items():
            if shabbat and daf_key(daf) < daf_key("9a"):
                continue

            segments = get_segments(daf_data)
            tractate_total += len(segments)

        if tractate_total:
            print(f"{path.stem:25} : {tractate_total:6} segments")
            total_remaining += tractate_total

            if shabbat:
                shabbat_remaining += tractate_total
            else:
                other_remaining += tractate_total

    print("-" * 60)
    print(f"Fichiers analysés              : {files_count}")
    print(f"Shabbat à partir de 9a         : {shabbat_remaining}")
    print(f"Autres traités                 : {other_remaining}")
    print(f"TOTAL segments restant         : {total_remaining}")

    if total_remaining:
        budget = 28.91
        budget_per_segment = budget / total_remaining
        print(f"Budget total                   : {budget:.2f} $")
        print(f"Budget maximal par segment     : {budget_per_segment:.8f} $")
    else:
        print("Aucun segment restant détecté.")


if __name__ == "__main__":
    main()
