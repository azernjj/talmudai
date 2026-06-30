import fs from "fs";
import path from "path";

const baseDir = "public/data/parashiot/commentaries";

const commentaries = [
  "onkelos",
  "sforno",
  "ramban"
];

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function splitText(text, maxLen = 1200) {
  const clean = String(text || "").trim();
  if (clean.length <= maxLen) return [clean];

  const parts = [];
  let current = "";

  for (const sentence of clean.split(/(?<=[.!?;:])\s+/)) {
    if ((current + " " + sentence).length > maxLen) {
      if (current.trim()) parts.push(current.trim());
      current = sentence;
    } else {
      current += " " + sentence;
    }
  }

  if (current.trim()) parts.push(current.trim());

  return parts.flatMap(part => {
    if (part.length <= maxLen) return [part];

    const chunks = [];
    for (let i = 0; i < part.length; i += maxLen) {
      chunks.push(part.slice(i, i + maxLen));
    }
    return chunks;
  });
}

async function googleTranslateChunk(text) {
  if (!text || !text.trim()) return "";

  const url =
    "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=fr&dt=t&q=" +
    encodeURIComponent(text);

  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const res = await fetch(url);

      if (!res.ok) {
        console.log(`Google erreur ${res.status}, tentative ${attempt}/5`);
        await delay(1500 * attempt);
        continue;
      }

      const data = await res.json();
      return (data[0] || []).map(x => x[0]).join("").trim();
    } catch (e) {
      console.log(`Erreur réseau, tentative ${attempt}/5 : ${e.message}`);
      await delay(1500 * attempt);
    }
  }

  return "";
}

async function googleTranslate(text) {
  const parts = splitText(text, 1200);
  const translated = [];

  for (const part of parts) {
    const t = await googleTranslateChunk(part);
    translated.push(t);
    await delay(350);
  }

  return translated.join(" ").trim();
}

function loadJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;

  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

async function translateFile(commentarySlug, file) {
  const inputFile = path.join(baseDir, commentarySlug, file);
  const outputFile = path.join(baseDir, commentarySlug, file.replace(".json", ".fr.json"));

  if (!fs.existsSync(inputFile)) return;
  if (file.endsWith(".fr.json")) return;

  const src = JSON.parse(fs.readFileSync(inputFile, "utf8"));

  const fr = loadJson(outputFile, {
    name: src.name,
    range: src.range,
    commentary: src.commentary,
    source: inputFile,
    verses: []
  });

  const frByRef = new Map((fr.verses || []).map(v => [v.ref, v]));
  const verses = [];

  console.log(`\n📘 ${commentarySlug} — ${file}`);

  for (const v of src.verses || []) {
    let frVerse = frByRef.get(v.ref);

    if (!frVerse) {
      frVerse = {
        ref: v.ref,
        fr: ""
      };
    }

    if (!frVerse.fr && v.en) {
      frVerse.fr = await googleTranslate(v.en);
      await delay(300);
    }

    verses.push(frVerse);

    fr.verses = verses;
    fs.writeFileSync(outputFile, JSON.stringify(fr, null, 2), "utf8");

    console.log(`${commentarySlug} ${file} ${v.ref} OK`);
  }

  console.log(`✅ ${outputFile}`);
}

async function translateCommentary(commentarySlug) {
  const dir = path.join(baseDir, commentarySlug);

  if (!fs.existsSync(dir)) {
    console.log(`Dossier introuvable : ${dir}`);
    return;
  }

  const files = fs.readdirSync(dir)
    .filter(f => f.endsWith(".json"))
    .filter(f => !f.endsWith(".fr.json"));

  for (const file of files) {
    await translateFile(commentarySlug, file);
  }
}

async function main() {
  for (const commentary of commentaries) {
    await translateCommentary(commentary);
  }

  console.log("\n✅ Traduction française Mikraot Guedolot terminée.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
