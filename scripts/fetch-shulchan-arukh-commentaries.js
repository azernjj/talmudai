import fs from "fs";
import path from "path";

const outBase = "public/data/shulchan-arukh/commentaries";
fs.mkdirSync(outBase, { recursive: true });

const section = {
  slug: "orach-chaim",
  sefaria: "Shulchan Arukh, Orach Chayim",
  maxSiman: 697
};

const commentaries = [
  {
    slug: "mishnah-berurah",
    title: "Mishnah Berurah",
    sefaria: "Mishnah Berurah"
  },
  {
    slug: "beur-halakha",
    title: "Beur Halakha",
    sefaria: "Biur Halacha"
  },
  {
    slug: "shaar-hatziyun",
    title: "Shaar HaTziyun",
    sefaria: "Sha'ar HaTziyun"
  },
  {
    slug: "magen-avraham",
    title: "Magen Avraham",
    sefaria: "Magen Avraham"
  },
  {
    slug: "taz",
    title: "Taz",
    sefaria: "Turei Zahav"
  },
  {
    slug: "baer-hetev",
    title: "Ba'er Hetev",
    sefaria: "Ba'er Hetev"
  }
];

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

  if (Array.isArray(raw)) {
    return raw.flat(Infinity).filter(Boolean).map(cleanHtml);
  }

  if (typeof raw === "string" && raw.trim()) {
    return [cleanHtml(raw)];
  }

  return [];
}

async function fetchCommentarySiman(commentary, simanNumber) {
  const ref = `${commentary.sefaria} on ${section.sefaria} ${simanNumber}`;

  const heData = await getText(ref, "he");
  await sleep(150);

  const enData = await getText(ref, "en");
  await sleep(150);

  const he = extractArray(heData, "he");
  const en = extractArray(enData, "en");

  const max = Math.max(he.length, en.length);
  if (!max) return null;

  return {
    siman: simanNumber,
    items: Array.from({ length: max }, (_, i) => ({
      id: i + 1,
      he: he[i] || "",
      en: en[i] || "",
      fr: ""
    }))
  };
}

async function processCommentary(commentary) {
  const dir = path.join(outBase, commentary.slug);
  fs.mkdirSync(dir, { recursive: true });

  const outPath = path.join(dir, `${section.slug}.json`);

  let output = {
    slug: commentary.slug,
    title: commentary.title,
    section: section.slug,
    sefaria: commentary.sefaria,
    simanim: []
  };

  if (fs.existsSync(outPath)) {
    try {
      const existing = JSON.parse(fs.readFileSync(outPath, "utf8"));
      if (existing?.simanim?.length) output = existing;
    } catch {}
  }

  const existingBySiman = new Map(output.simanim.map(s => [s.siman, s]));

  console.log(`\n📘 ${commentary.title}`);

  for (let n = 1; n <= section.maxSiman; n++) {
    if (existingBySiman.has(n) && existingBySiman.get(n).items?.length) {
      console.log(`✓ Siman ${n} déjà présent`);
      continue;
    }

    const siman = await fetchCommentarySiman(commentary, n);

    if (!siman) {
      console.log(`- Siman ${n} vide`);
      continue;
    }

    existingBySiman.set(n, siman);

    output.simanim = Array.from(existingBySiman.values())
      .sort((a, b) => a.siman - b.siman);

    fs.writeFileSync(outPath, JSON.stringify(output, null, 2), "utf8");

    console.log(`✓ Siman ${n} : ${siman.items.length} commentaires`);
  }

  console.log(`✅ ${outPath}`);
}

async function main() {
  for (const commentary of commentaries) {
    await processCommentary(commentary);
  }

  console.log("\n✅ Commentaires Orah Haïm terminés.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
