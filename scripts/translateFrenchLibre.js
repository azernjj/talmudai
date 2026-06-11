import fs from "fs";

const masechet = process.argv[2] || "berakhot";
const input = `public/data/merged/${masechet}.json`;

const API_URL = process.env.LIBRETRANSLATE_URL || "https://libretranslate.com/translate";
const API_KEY = process.env.LIBRETRANSLATE_API_KEY || "";

function cleanHtml(text) {
  return String(text || "")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function fixGlossary(text) {
  return text
    .replaceAll("prêtres", "Cohanim")
    .replaceAll("Prêtres", "Cohanim")
    .replaceAll("offrande", "térouma")
    .replaceAll("Shema", "Chéma")
    .replaceAll("Mishna", "Michna")
    .replaceAll("Gemara", "Guemara");
}

async function translate(text) {
  const body = {
    q: text,
    source: "en",
    target: "fr",
    format: "text"
  };

  if (API_KEY) body.api_key = API_KEY;

  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    throw new Error(`LibreTranslate erreur ${res.status}: ${await res.text()}`);
  }

  const data = await res.json();
  return fixGlossary(data.translatedText || "");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  if (!fs.existsSync(input)) {
    console.error("Fichier introuvable :", input);
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(input, "utf8"));

  for (const [daf, dafData] of Object.entries(data.dapim || {})) {
    console.log("Daf :", daf);

    for (const seg of dafData.segments || []) {
      if (seg.fr && seg.fr.trim()) continue;
      if (!seg.en) continue;

      const english = cleanHtml(seg.en);
      if (!english) continue;

      try {
        seg.fr = await translate(english);
        console.log(`  Segment ${seg.id} OK`);
        await sleep(1200);
      } catch (e) {
        console.log(`  Segment ${seg.id} erreur :`, e.message);
        fs.writeFileSync(input, JSON.stringify(data), "utf8");
        process.exit(1);
      }
    }

    fs.writeFileSync(input, JSON.stringify(data), "utf8");
  }

  console.log("Traduction terminée :", input);
}

main();
