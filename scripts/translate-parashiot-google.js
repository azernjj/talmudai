import fs from "fs";
import path from "path";

const inputDir = "public/data/parashiot";
const delay = ms => new Promise(r => setTimeout(r, ms));

async function googleTranslate(text) {
  if (!text || !text.trim()) return "";

  const url =
    "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=fr&dt=t&q=" +
    encodeURIComponent(text);

  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const res = await fetch(url);

      if (!res.ok) {
        console.log(`Google erreur ${res.status}, tentative ${attempt}/5`);
        await delay(1000 * attempt);
        continue;
      }

      const data = await res.json();
      return (data[0] || []).map(x => x[0]).join("").trim();
    } catch (e) {
      console.log(`Erreur réseau Google, tentative ${attempt}/5 : ${e.message}`);
      await delay(1000 * attempt);
    }
  }

  console.log("Échec traduction, segment laissé vide.");
  return "";
}

async function processFile(file) {
  if (file === "index.json" || file.endsWith(".fr.json")) return;

  const srcPath = path.join(inputDir, file);
  const outPath = path.join(inputDir, file.replace(".json", ".fr.json"));

  const src = JSON.parse(fs.readFileSync(srcPath, "utf8"));
  let fr = fs.existsSync(outPath)
    ? JSON.parse(fs.readFileSync(outPath, "utf8"))
    : { name: src.name, range: src.range, verses: [] };

  const byRef = new Map((fr.verses || []).map(v => [v.ref, v]));

  const verses = [];

  for (const v of src.verses || []) {
    const existing = byRef.get(v.ref) || { ref: v.ref, fr: "", rashi: [] };

    if (!existing.fr && v.en) {
      existing.fr = await googleTranslate(v.en);
      await delay(150);
    }

    const existingRashi = existing.rashi || [];
    existing.rashi = [];

    for (let i = 0; i < (v.rashi || []).length; i++) {
      const old = existingRashi[i] || { id: i + 1, fr: "" };
      const r = v.rashi[i];

      if (!old.fr && r.en) {
        old.fr = await googleTranslate(r.en);
        await delay(150);
      }

      existing.rashi.push(old);
    }

    verses.push(existing);

    fs.writeFileSync(outPath, JSON.stringify({
      name: src.name,
      range: src.range,
      verses
    }, null, 2), "utf8");

    console.log(`${file} ${v.ref} OK`);
  }

  console.log(`✅ ${outPath}`);
}

for (const file of fs.readdirSync(inputDir)) {
  if (file.endsWith(".json")) {
    await processFile(file);
  }
}

console.log("✅ Traduction française des parachiot terminée.");
