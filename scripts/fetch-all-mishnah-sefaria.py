#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


OUTPUT_DIR = Path("public/data/mishna")
API_BASE = "https://www.sefaria.org/api/v3/texts"


TRACTATES = [
    # Zeraïm
    {"seder": "Zeraïm", "title": "Mishnah Berakhot", "name": "Berakhot", "file": "berakhot.json"},
    {"seder": "Zeraïm", "title": "Mishnah Peah", "name": "Péa", "file": "peah.json"},
    {"seder": "Zeraïm", "title": "Mishnah Demai", "name": "Demaï", "file": "demai.json"},
    {"seder": "Zeraïm", "title": "Mishnah Kilayim", "name": "Kilaïm", "file": "kilayim.json"},
    {"seder": "Zeraïm", "title": "Mishnah Sheviit", "name": "Cheviit", "file": "sheviit.json"},
    {"seder": "Zeraïm", "title": "Mishnah Terumot", "name": "Teroumot", "file": "terumot.json"},
    {"seder": "Zeraïm", "title": "Mishnah Maasrot", "name": "Maasserot", "file": "maaserot.json"},
    {"seder": "Zeraïm", "title": "Mishnah Maaser Sheni", "name": "Maasser Chéni", "file": "maaser-sheni.json"},
    {"seder": "Zeraïm", "title": "Mishnah Challah", "name": "Halla", "file": "challah.json"},
    {"seder": "Zeraïm", "title": "Mishnah Orlah", "name": "Orla", "file": "orlah.json"},
    {"seder": "Zeraïm", "title": "Mishnah Bikkurim", "name": "Bikourim", "file": "bikkurim.json"},

    # Moed
    {"seder": "Moed", "title": "Mishnah Shabbat", "name": "Chabbat", "file": "shabbat.json"},
    {"seder": "Moed", "title": "Mishnah Eruvin", "name": "Erouvin", "file": "eruvin.json"},
    {"seder": "Moed", "title": "Mishnah Pesachim", "name": "Pessa'him", "file": "pesachim.json"},
    {"seder": "Moed", "title": "Mishnah Shekalim", "name": "Chekalim", "file": "shekalim.json"},
    {"seder": "Moed", "title": "Mishnah Yoma", "name": "Yoma", "file": "yoma.json"},
    {"seder": "Moed", "title": "Mishnah Sukkah", "name": "Soukka", "file": "sukkah.json"},
    {"seder": "Moed", "title": "Mishnah Beitzah", "name": "Beitsa", "file": "beitzah.json"},
    {"seder": "Moed", "title": "Mishnah Rosh Hashanah", "name": "Roch Hachana", "file": "rosh-hashanah.json"},
    {"seder": "Moed", "title": "Mishnah Taanit", "name": "Taanit", "file": "taanit.json"},
    {"seder": "Moed", "title": "Mishnah Megillah", "name": "Méguila", "file": "megillah.json"},
    {"seder": "Moed", "title": "Mishnah Moed Katan", "name": "Moed Katan", "file": "moed-katan.json"},
    {"seder": "Moed", "title": "Mishnah Chagigah", "name": "Haguiga", "file": "chagigah.json"},

    # Nachim
    {"seder": "Nachim", "title": "Mishnah Yevamot", "name": "Yevamot", "file": "yevamot.json"},
    {"seder": "Nachim", "title": "Mishnah Ketubot", "name": "Ketoubot", "file": "ketubot.json"},
    {"seder": "Nachim", "title": "Mishnah Nedarim", "name": "Nedarim", "file": "nedarim.json"},
    {"seder": "Nachim", "title": "Mishnah Nazir", "name": "Nazir", "file": "nazir.json"},
    {"seder": "Nachim", "title": "Mishnah Sotah", "name": "Sota", "file": "sotah.json"},
    {"seder": "Nachim", "title": "Mishnah Gittin", "name": "Guitin", "file": "gittin.json"},
    {"seder": "Nachim", "title": "Mishnah Kiddushin", "name": "Kidouchin", "file": "kiddushin.json"},

    # Nezikin
    {"seder": "Nezikin", "title": "Mishnah Bava Kamma", "name": "Bava Kama", "file": "bava-kamma.json"},
    {"seder": "Nezikin", "title": "Mishnah Bava Metzia", "name": "Bava Metsia", "file": "bava-metzia.json"},
    {"seder": "Nezikin", "title": "Mishnah Bava Batra", "name": "Bava Batra", "file": "bava-batra.json"},
    {"seder": "Nezikin", "title": "Mishnah Sanhedrin", "name": "Sanhédrin", "file": "sanhedrin.json"},
    {"seder": "Nezikin", "title": "Mishnah Makkot", "name": "Makot", "file": "makkot.json"},
    {"seder": "Nezikin", "title": "Mishnah Shevuot", "name": "Chevouot", "file": "shevuot.json"},
    {"seder": "Nezikin", "title": "Mishnah Eduyot", "name": "Edouyot", "file": "eduyot.json"},
    {"seder": "Nezikin", "title": "Mishnah Avodah Zarah", "name": "Avoda Zara", "file": "avodah-zarah.json"},
    {"seder": "Nezikin", "title": "Pirkei Avot", "name": "Pirké Avot", "file": "pirkei-avot.json"},
    {"seder": "Nezikin", "title": "Mishnah Horayot", "name": "Horayot", "file": "horayot.json"},

    # Kodachim
    {"seder": "Kodachim", "title": "Mishnah Zevachim", "name": "Zevahim", "file": "zevachim.json"},
    {"seder": "Kodachim", "title": "Mishnah Menachot", "name": "Menahot", "file": "menachot.json"},
    {"seder": "Kodachim", "title": "Mishnah Chullin", "name": "Houlin", "file": "chullin.json"},
    {"seder": "Kodachim", "title": "Mishnah Bekhorot", "name": "Bekhorot", "file": "bekhorot.json"},
    {"seder": "Kodachim", "title": "Mishnah Arakhin", "name": "Arakhin", "file": "arakhin.json"},
    {"seder": "Kodachim", "title": "Mishnah Temurah", "name": "Temoura", "file": "temurah.json"},
    {"seder": "Kodachim", "title": "Mishnah Keritot", "name": "Keritot", "file": "keritot.json"},
    {"seder": "Kodachim", "title": "Mishnah Meilah", "name": "Méila", "file": "meilah.json"},
    {"seder": "Kodachim", "title": "Mishnah Tamid", "name": "Tamid", "file": "tamid.json"},
    {"seder": "Kodachim", "title": "Mishnah Middot", "name": "Midot", "file": "middot.json"},
    {"seder": "Kodachim", "title": "Mishnah Kinnim", "name": "Kinim", "file": "kinnim.json"},

    # Taharot
    {"seder": "Taharot", "title": "Mishnah Kelim", "name": "Kélim", "file": "kelim.json"},
    {"seder": "Taharot", "title": "Mishnah Oholot", "name": "Oholot", "file": "oholot.json"},
    {"seder": "Taharot", "title": "Mishnah Negaim", "name": "Négaïm", "file": "negaim.json"},
    {"seder": "Taharot", "title": "Mishnah Parah", "name": "Para", "file": "parah.json"},
    {"seder": "Taharot", "title": "Mishnah Tahorot", "name": "Taharot", "file": "tahorot.json"},
    {"seder": "Taharot", "title": "Mishnah Mikvaot", "name": "Mikvaot", "file": "mikvaot.json"},
    {"seder": "Taharot", "title": "Mishnah Niddah", "name": "Nidda", "file": "niddah.json"},
    {"seder": "Taharot", "title": "Mishnah Makhshirin", "name": "Makhchirin", "file": "makhshirin.json"},
    {"seder": "Taharot", "title": "Mishnah Zavim", "name": "Zavim", "file": "zavim.json"},
    {"seder": "Taharot", "title": "Mishnah Tevul Yom", "name": "Tevoul Yom", "file": "tevul-yom.json"},
    {"seder": "Taharot", "title": "Mishnah Yadayim", "name": "Yadaïm", "file": "yadayim.json"},
    {"seder": "Taharot", "title": "Mishnah Oktzin", "name": "Ouktsin", "file": "uktzin.json"},
]


def strip_html(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    return re.sub(r"[ \t]+", " ", text).strip()


def is_sequence(value: Any) -> bool:
    return isinstance(value, list)


def get_version_text(data: dict[str, Any], language: str) -> Any:
    versions = data.get("versions") or []

    for version in versions:
        if not isinstance(version, dict):
            continue

        lang = str(
            version.get("language")
            or version.get("lang")
            or version.get("actualLanguage")
            or ""
        ).lower()

        if lang == language.lower():
            return version.get("text")

    # Compatibilité avec certaines réponses historiques.
    if language == "he":
        return data.get("he")
    if language == "en":
        return data.get("text")

    return None


def normalize_chapters(he_text: Any, en_text: Any, sefaria_title: str) -> dict[str, Any]:
    if not isinstance(he_text, list):
        raise ValueError("Le texte hébreu reçu n'est pas une liste de chapitres.")

    chapters: dict[str, Any] = {}

    for chapter_index, he_chapter in enumerate(he_text, start=1):
        if not isinstance(he_chapter, list):
            he_chapter = [he_chapter]

        en_chapter = []
        if isinstance(en_text, list) and chapter_index - 1 < len(en_text):
            possible = en_text[chapter_index - 1]
            en_chapter = possible if isinstance(possible, list) else [possible]

        mishnayot = []

        for mishna_index, he_segment in enumerate(he_chapter, start=1):
            en_segment = (
                en_chapter[mishna_index - 1]
                if mishna_index - 1 < len(en_chapter)
                else ""
            )

            ref = f"{sefaria_title} {chapter_index}:{mishna_index}"

            mishnayot.append(
                {
                    "id": f"{chapter_index}:{mishna_index}",
                    "chapter": chapter_index,
                    "mishna": mishna_index,
                    "ref": ref,
                    "he": strip_html(he_segment),
                    "en": strip_html(en_segment),
                    "fr": "",
                    "etude_fr": None,
                }
            )

        chapters[str(chapter_index)] = {
            "chapter": chapter_index,
            "mishnayot": mishnayot,
        }

    return chapters


def fetch_json(session: requests.Session, title: str, retries: int, timeout: int) -> dict[str, Any]:
    encoded = quote(title, safe="")
    url = f"{API_BASE}/{encoded}"

    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = session.get(
                url,
                timeout=timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "TALMUD-AI-Mishnah-Importer/1.0",
                },
            )

            if response.status_code == 429:
                wait = min(10 * attempt, 60)
                print(f"   ⚠️ Limite Sefaria, attente {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except Exception as exc:
            last_error = exc
            if attempt < retries:
                wait = min(2 ** attempt, 20)
                print(f"   ⚠️ Tentative {attempt}/{retries} échouée, attente {wait}s : {exc}")
                time.sleep(wait)

    raise RuntimeError(f"Échec Sefaria pour {title}: {last_error}")


def save_json(path: Path, data: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def build_index(downloaded: list[dict[str, Any]]) -> None:
    index = [
        {
            "seder": item["seder"],
            "name": item["name"],
            "title": item["title"],
            "file": item["file"],
        }
        for item in downloaded
    ]

    save_json(OUTPUT_DIR / "index.json", index)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Récupère les 63 traités de Michna depuis Sefaria."
    )
    parser.add_argument(
        "--only",
        default="",
        help="Limiter à un fichier ou nom, ex. berakhot ou 'Mishnah Berakhot'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limiter le nombre de traités téléchargés.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retélécharger les fichiers déjà présents.",
    )
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--delay", type=float, default=0.8)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    selected = TRACTATES

    if args.only:
        needle = args.only.lower().strip()
        selected = [
            item for item in selected
            if needle in item["file"].lower()
            or needle in item["name"].lower()
            or needle in item["title"].lower()
        ]

    if args.limit > 0:
        selected = selected[: args.limit]

    if not selected:
        print("❌ Aucun traité correspondant.", file=sys.stderr)
        return 2

    session = requests.Session()
    successful: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    print(f"📚 Traités sélectionnés : {len(selected)}")
    print(f"📁 Destination : {OUTPUT_DIR}")

    for position, tractate in enumerate(selected, start=1):
        output_file = OUTPUT_DIR / tractate["file"]

        if output_file.exists() and not args.force:
            print(f"[{position}/{len(selected)}] ⏭️ {tractate['name']} déjà présent.")
            successful.append(tractate)
            continue

        print(f"[{position}/{len(selected)}] 📥 {tractate['title']}")

        try:
            api_data = fetch_json(
                session=session,
                title=tractate["title"],
                retries=max(1, args.retries),
                timeout=max(10, args.timeout),
            )

            he_text = get_version_text(api_data, "he")
            en_text = get_version_text(api_data, "en")

            if not he_text:
                raise ValueError("Aucune version hébraïque détectée dans la réponse.")

            chapters = normalize_chapters(
                he_text=he_text,
                en_text=en_text,
                sefaria_title=tractate["title"],
            )

            total_mishnayot = sum(
                len(chapter["mishnayot"])
                for chapter in chapters.values()
            )

            result = {
                "type": "mishna",
                "title": tractate["name"],
                "sefaria_title": tractate["title"],
                "seder": tractate["seder"],
                "source": "Sefaria",
                "chapters": chapters,
                "stats": {
                    "chapters": len(chapters),
                    "mishnayot": total_mishnayot,
                    "translated_fr": 0,
                },
            }

            save_json(output_file, result)
            successful.append(tractate)

            print(
                f"   ✅ {len(chapters)} chapitre(s), "
                f"{total_mishnayot} Michna(yot)"
            )

        except Exception as exc:
            failures.append(
                {
                    "title": tractate["title"],
                    "file": tractate["file"],
                    "error": str(exc),
                }
            )
            print(f"   ❌ {exc}")

        build_index(successful)
        time.sleep(max(0, args.delay))

    save_json(
        OUTPUT_DIR / "download-report.json",
        {
            "successful": len(successful),
            "failed": len(failures),
            "failures": failures,
        },
    )

    print("\n==================================================")
    print(f"✅ Réussis : {len(successful)}")
    print(f"❌ Échecs  : {len(failures)}")
    print(f"📄 Index   : {OUTPUT_DIR / 'index.json'}")
    print("==================================================")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
