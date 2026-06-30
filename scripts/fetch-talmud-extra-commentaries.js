import fs from "fs";
import path from "path";

const mergedDir = "public/data/merged";
const outBase = "public/data/commentaries";

const commentaries = [
  {
    slug: "ritva",
    title: "Ritva",
    sefaria: "Ritva"
  }
];

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function cleanHtml(str = "") {
  return String(str)
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function titleFromFile(file) {
  return file
    .replace(".json", "")
    .split("-")
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
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

function extractItems(data, lang) {
  const raw = lang === "he" ? data?.he : data?.text;

  if (Array.isArray(raw)) {
    return raw
      .flat(Infinity)
      .filter(Boolean)
      .map(cleanHtml)
      .filter(Boolean);
  }

  if (typeof raw === "string" && raw.trim()) {
    return [cleanHtml(raw)];
  }

  return [];
}

async function fetchCommentaryDaf(commentary, masechetTitle, daf) {
  const ref = `${commentary.sefaria} on ${masechetTitle} ${daf}`;

  const heData = await fetchSefaria(ref, "he");
  await delay(150);

  const enData = await fetchSefaria(ref, "en");
  await delay(150);

  const he = extractItems(heData, "he");
  const en = extractItems(enData, "en");

  const max = Math.max(he.length, en.length);
  if (!max) return null;

  return {
    daf,
    comments: Array.from({ length: max }, (_, i) => ({
      id: i + 1,
      he: he[i] || "",
      en: en[i] || "",
      fr: ""
    }))
  };
}

async function processMasechet(commentary, file) {
  const srcPath = path.join(mergedDir, file);
  const src = JSON.parse(fs.readFileSync(srcPath, "utf8"));

  const masechetTitle = src.title || titleFromFile(file);
  const outDir = path.join(outBase, commentary.slug);
  const outPath = path.join(outDir, file);

  fs.mkdirSync(outDir, { recursive: true });

  let output = {
    slug: commentary.slug,
    title: commentary.title,
    masechet: masechetTitle,
    file,
    dapim: []
  };

  if (fs.existsSync(outPath)) {
    try {
      const existing = JSON.parse(fs.readFileSync(outPath, "utf8"));
      if (existing?.dapim?.length) output = existing;
    } catch {}
  }

  const existingByDaf = new Map(output.dapim.map(d => [d.daf, d]));
  const dapim = Object.keys(src.dapim || {}).sort((a, b) => {
    const na = parseFloat(a);
    const nb = parseFloat(b);
    if (na !== nb) return na - nb;
    return a.localeCompare(b);
  });

  console.log(`\n📘 ${commentary.title} — ${masechetTitle}`);

  for (const daf of dapim) {
    if (existingByDaf.has(daf) && existingByDaf.get(daf).comments?.length) {
      console.log(`✓ ${masechetTitle} ${daf} déjà présent`);
      continue;
    }

    const dafData = await fetchCommentaryDaf(commentary, masechetTitle, daf);

    if (!dafData) {
      console.log(`- ${masechetTitle} ${daf} vide`);
      continue;
    }

    existingByDaf.set(daf, dafData);

    output.dapim = Array.from(existingByDaf.values())
      .sort((a, b) => {
        const na = parseFloat(a.daf);
        const nb = parseFloat(b.daf);
        if (na !== nb) return na - nb;
        return a.daf.localeCompare(b.daf);
      });

    fs.writeFileSync(outPath, JSON.stringify(output, null, 2), "utf8");

    console.log(`✓ ${masechetTitle} ${daf} : ${dafData.comments.length} commentaires`);
  }

  console.log(`✅ ${outPath}`);
}

async function main() {
  const files = fs.readdirSync(mergedDir)
    .filter(f => f.endsWith(".json"))
    .sort();

  for (const commentary of commentaries) {
    for (const file of files) {
      await processMasechet(commentary, file);
    }
  }

  console.log("\n✅ Ritva terminé.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
