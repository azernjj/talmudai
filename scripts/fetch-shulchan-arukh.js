import fs from "fs";
import path from "path";

const outDir = "public/data/shulchan-arukh";
fs.mkdirSync(outDir, { recursive: true });

const section = {
  slug: "orach-chaim",
  title: "Orach Chayim",
  heTitle: "אורח חיים",
  sefaria: "Shulchan Arukh, Orach Chayim",
  maxSiman: 697
};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function cleanHtml(str = "") {
  return String(str)
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function getText(ref, lang = "he") {
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}?lang=${lang}&context=0&commentary=0`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.log(`- ${ref} ${lang} : ${res.status}`);
      return null;
    }
    return await res.json();
  } catch (e) {
    console.log(`- ${ref} ${lang} : ${e.message}`);
    return null;
  }
}

function extractArray(data, lang) {
  const raw = lang === "he" ? data?.he : data?.text;

  if (Array.isArray(raw)) return raw.flat(Infinity).filter(Boolean).map(cleanHtml);
  if (typeof raw === "string" && raw.trim()) return [cleanHtml(raw)];

  return [];
}

async function fetchSiman(n) {
  const ref = `${section.sefaria} ${n}`;

  const heData = await getText(ref, "he");
  await sleep(150);

  const enData = await getText(ref, "en");
  await sleep(150);

  const he = extractArray(heData, "he");
  const en = extractArray(enData, "en");

  const max = Math.max(he.length, en.length);

  if (!max) return null;

  return {
    siman: n,
    title: "",
    seifim: Array.from({ length: max }, (_, i) => ({
      seif: i + 1,
      he: he[i] || "",
      en: en[i] || "",
      fr: "",
      commentaries: {}
    }))
  };
}

async function main() {
  const outPath = path.join(outDir, `${section.slug}.json`);

  let output = {
    slug: section.slug,
    title: section.title,
    heTitle: section.heTitle,
    sefaria: section.sefaria,
    simanim: []
  };

  if (fs.existsSync(outPath)) {
    try {
      const existing = JSON.parse(fs.readFileSync(outPath, "utf8"));
      if (existing?.simanim?.length) output = existing;
    } catch {}
  }

  const existingBySiman = new Map(output.simanim.map(s => [s.siman, s]));

  for (let n = 1; n <= section.maxSiman; n++) {
    if (existingBySiman.has(n) && existingBySiman.get(n).seifim?.length) {
      console.log(`✓ Siman ${n} déjà présent`);
      continue;
    }

    const siman = await fetchSiman(n);

    if (!siman) {
      console.log(`- Siman ${n} vide`);
      continue;
    }

    existingBySiman.set(n, siman);

    output.simanim = Array.from(existingBySiman.values())
      .sort((a, b) => a.siman - b.siman);

    fs.writeFileSync(outPath, JSON.stringify(output, null, 2), "utf8");

    console.log(`✓ Siman ${n} : ${siman.seifim.length} seifim`);
  }

  fs.writeFileSync(
    path.join(outDir, "index.json"),
    JSON.stringify([{
      slug: section.slug,
      title: section.title,
      heTitle: section.heTitle,
      file: `${section.slug}.json`
    }], null, 2),
    "utf8"
  );

  console.log("\n✅ Orach Chayim terminé.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
