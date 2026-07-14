#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import re
from pathlib import Path

BAD = {
    "html": re.compile(r"<\/?[a-zA-Z][^>]*>"),
    "tag technique": re.compile(r"TAG\d*(?:FIN)?", re.I),
    "anglais résiduel": re.compile(r"\b(?:the|and|with|should|would|could|rather|moreover|so|it)\b", re.I),
    "français suspect": re.compile(r"\b(?:A un certain|tu t'impliques-tu|ce le verset)\b", re.I),
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True)
    p.add_argument("--report", default="logs/translation_quality_report.json")
    args = p.parse_args()

    path = Path(args.file)
    data = json.loads(path.read_text(encoding="utf-8"))
    issues = []

    for daf, daf_obj in data.get("dapim", {}).items():
        for index, segment in enumerate(daf_obj.get("segments", [])):
            fr = str(segment.get("fr", ""))
            he = str(segment.get("he", ""))
            for name, rx in BAD.items():
                if rx.search(fr):
                    issues.append({
                        "daf": daf,
                        "segment_id": segment.get("id", index + 1),
                        "type": name,
                        "fr": fr[:500],
                    })
            if "אוֹר" in he and re.search(r"\b(?:le terme )?ou\b", fr, re.I):
                issues.append({
                    "daf": daf,
                    "segment_id": segment.get("id", index + 1),
                    "type": "confusion אוֹר / ou",
                    "fr": fr[:500],
                })

    report = {"file": str(path), "issues_count": len(issues), "issues": issues}
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Problèmes détectés : {len(issues)}")
    print(f"Rapport : {report_path}")


if __name__ == "__main__":
    main()
