import fs from "fs";
import path from "path";

const baseDir = "public/data/shulchan-arukh/commentaries";

const commentaries = [
  "baer-hetev",
  "taz",
  "beur-halakha",
  "magen-avraham",
  "mishnah-berurah"
];

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

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

  console.log("Échec traduction, texte laissé vide.");
  return "";
}

function loadJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;

  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

async function translateCommentary(slug) {
  const inputFile = path.join(baseDir, slug, "orach-chaim.json");
  const outputFile = path.join(baseDir, slug, "orach-chaim.fr.json");

  if (!fs.existsSync(inputFile)) {
    console.log(`Fichier introuvable : ${inputFile}`);
    return;
  }

  const src = JSON.parse(fs.readFileSync(inputFile, "utf8"));

  const fr = loadJson(outputFile, {
    slug: src.slug,
    title: src.title,
    section: src.section,
    source: inputFile,
    simanim: []
  });

  const frBySiman = new Map((fr.simanim || []).map(s => [s.siman, s]));

  console.log(`\n📘 Traduction : ${src.title}`);

  for (const siman of src.simanim || []) {
    let frSiman = frBySiman.get(siman.siman);

    if (!frSiman) {
      frSiman = {
        siman: siman.siman,
        items: []
      };
      frBySiman.set(siman.siman, frSiman);
    }

    const frById = new Map((frSiman.items || []).map(item => [item.id, item]));
    const items = [];

    for (const item of siman.items || []) {
      let frItem = frById.get(item.id);

      if (!frItem) {
        frItem = {
          id: item.id,
          fr: ""
        };
      }

      if (!frItem.fr && item.en) {
        frItem.fr = await googleTranslate(item.en);
        await delay(300);
      }

      items.push(frItem);
      console.log(`${src.title} ${siman.siman}:${item.id} OK`);
    }

    frSiman.items = items;

    fr.simanim = Array.from(frBySiman.values())
      .sort((a, b) => a.siman - b.siman);

    fs.writeFileSync(outputFile, JSON.stringify(fr, null, 2), "utf8");

    console.log(`✅ ${src.title} — Siman ${siman.siman} sauvegardé`);
  }

  console.log(`✅ Fichier terminé : ${outputFile}`);
}

async function main() {
  for (const slug of commentaries) {
    await translateCommentary(slug);
  }

  console.log("\n✅ Traduction française des commentaires terminée.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
