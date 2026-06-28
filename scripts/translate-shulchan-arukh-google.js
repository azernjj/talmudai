import fs from "fs";
import path from "path";

const inputFile = "public/data/shulchan-arukh/orach-chaim.json";
const outputFile = "public/data/shulchan-arukh/orach-chaim.fr.json";

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
        await delay(1000 * attempt);
        continue;
      }

      const data = await res.json();
      return (data[0] || []).map(x => x[0]).join("").trim();
    } catch (e) {
      console.log(`Erreur réseau, tentative ${attempt}/5 : ${e.message}`);
      await delay(1000 * attempt);
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

async function main() {
  if (!fs.existsSync(inputFile)) {
    throw new Error(`Fichier introuvable : ${inputFile}`);
  }

  const src = JSON.parse(fs.readFileSync(inputFile, "utf8"));

  const fr = loadJson(outputFile, {
    slug: src.slug,
    title: src.title,
    heTitle: src.heTitle,
    source: inputFile,
    simanim: []
  });

  const frBySiman = new Map((fr.simanim || []).map(s => [s.siman, s]));

  for (const siman of src.simanim || []) {
    let frSiman = frBySiman.get(siman.siman);

    if (!frSiman) {
      frSiman = {
        siman: siman.siman,
        title: siman.title || "",
        seifim: []
      };
      frBySiman.set(siman.siman, frSiman);
    }

    const frBySeif = new Map((frSiman.seifim || []).map(s => [s.seif, s]));
    const seifim = [];

    for (const seif of siman.seifim || []) {
      let frSeif = frBySeif.get(seif.seif);

      if (!frSeif) {
        frSeif = {
          seif: seif.seif,
          fr: ""
        };
      }

      if (!frSeif.fr && seif.en) {
        frSeif.fr = await googleTranslate(seif.en);
        await delay(250);
      }

      seifim.push(frSeif);
      console.log(`Orah Haïm ${siman.siman}:${seif.seif} OK`);
    }

    frSiman.seifim = seifim;

    fr.simanim = Array.from(frBySiman.values())
      .sort((a, b) => a.siman - b.siman);

    fs.writeFileSync(outputFile, JSON.stringify(fr, null, 2), "utf8");

    console.log(`✅ Siman ${siman.siman} sauvegardé`);
  }

  console.log("✅ Traduction française Orah Haïm terminée.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
