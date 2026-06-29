import fs from "fs";
import path from "path";

const parashiotDir = "public/data/parashiot";
const outBase = "public/data/parashiot/commentaries";

const commentaries = [
  {
    slug: "sforno",
    title: "Sforno",
    sefaria: "Sforno"
  },
  {
    slug: "ramban",
    title: "Ramban",
    sefaria: "Ramban"
  }
];

const delay = ms => new Promise(r => setTimeout(r, ms));

function cleanHtml(str = "") {
  return String(str)
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function fetchSefaria(ref, lang = "he") {
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}?lang=${lang}&context=0&commentary=0`;

  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const res = await fetch(url);

      if (!res.ok) {
        console.log(`Erreur ${res.status} : ${ref}`);
        await delay(1000 * attempt);
        continue;
      }

      return await res.json();
    } catch (e) {
      console.log(`Erreur réseau ${attempt}/5 : ${e.message}`);
      await delay(1000 * attempt);
    }
  }

  return null;
}

function extractText(data, lang) {
  const raw = lang === "he" ? data?.he : data?.text;

  if (Array.isArray(raw)) {
    return raw.flat(Infinity).filter(Boolean).map(cleanHtml).join(" ");
  }

  if (typeof raw === "string") return cleanHtml(raw);

  return "";
}

async function fetchCommentaryForParasha(commentary, file) {
  if (file === "index.json" || file.endsWith(".fr.json")) return;

  const srcPath = path.join(parashiotDir, file);
  const outDir = path.join(outBase, commentary.slug);
  const outPath = path.join(outDir, file);

  fs.mkdirSync(outDir, { recursive: true });

  const parasha = JSON.parse(fs.readFileSync(srcPath, "utf8"));

  let output = fs.existsSync(outPath)
    ? JSON.parse(fs.readFileSync(outPath, "utf8"))
    : {
        name: parasha.name,
        range: parasha.range,
        commentary: commentary.title,
        verses: []
      };

  const byRef = new Map((output.verses || []).map(v => [v.ref, v]));
  const verses = [];

  console.log(`\n📖 ${parasha.name} — ${commentary.title}`);

  for (const v of parasha.verses || []) {
    const existing = byRef.get(v.ref) || {
      ref: v.ref,
      he: "",
      en: "",
      fr: ""
    };

    if (!existing.he) {
      const ref = `${commentary.sefaria} on ${v.ref}`;
      const heData = await fetchSefaria(ref, "he");
      existing.he = extractText(heData, "he");
      await delay(150);
    }

    if (!existing.en) {
      const ref = `${commentary.sefaria} on ${v.ref}`;
      const enData = await fetchSefaria(ref, "en");
      existing.en = extractText(enData, "en");
      await delay(150);
    }

    verses.push(existing);

    output.verses = verses;
    fs.writeFileSync(outPath, JSON.stringify(output, null, 2), "utf8");

    console.log(`✓ ${v.ref} ${commentary.title}`);
  }

  console.log(`✅ ${outPath}`);
}

async function main() {
  const files = fs.readdirSync(parashiotDir)
    .filter(f => f.endsWith(".json"))
    .filter(f => f !== "index.json")
    .filter(f => !f.endsWith(".fr.json"));

  for (const commentary of commentaries) {
    for (const file of files) {
      await fetchCommentaryForParasha(commentary, file);
    }
  }

  console.log("\n✅ Sforno + Ramban terminés.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
