#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

def atomic_save(path: Path, data):
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

def main():
    p = argparse.ArgumentParser(description="Répare sans API les translittérations ashmoura/ashmura.")
    p.add_argument("--file", required=True)
    p.add_argument("--daf", default="2a")
    p.add_argument("--segment", type=int, default=1)
    args = p.parse_args()

    path = Path(args.file)
    data = json.loads(path.read_text(encoding="utf-8"))
    segments = data["dapim"][args.daf]["segments"]
    target = None
    for s in segments:
        if int(s.get("id", -1)) == args.segment:
            target = s
            break
    if target is None:
        raise SystemExit("Segment introuvable.")

    old = str(target.get("fr", ""))
    new = re.sub(r"\bashmou?ra\b|\bashmura\b", "garde", old, flags=re.IGNORECASE)
    target["fr"] = new
    target.setdefault("translation_review", {}).setdefault("corrections", []).append(
        "Correction locale sans API : ashmoura/ashmura remplacé par « garde »."
    )
    atomic_save(path, data)

    print("Avant :", old)
    print("Après :", new)
    print("✅ Correction enregistrée sans appel API.")

if __name__ == "__main__":
    main()
