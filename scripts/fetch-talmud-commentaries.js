import fs from "fs";
import path from "path";

const mergedDir = "public/data/merged";
const outBase = "public/data/commentaries";

const commentaries = [
  {
    slug: "rosh",
    title: "Roch",
    sefaria: "Rosh"
  }
];

const masechetMap = {
  "berakhot.json": "Berakhot",
  "shabbat.json": "Shabbat",
  "eruvin.json": "Eruvin",
  "pesachim.json": "Pesachim",
  "yoma.json": "Yoma",
  "sukkah.json": "Sukkah",
  "beitzah.json": "Beitzah",
  "rosh-hashanah.json": "Rosh Hashanah",
  "taanit.json": "Taanit",
  "megillah.json": "Megillah",
  "moed-katan.json": "Moed Katan",
  "chagigah.json": "Chagigah",
  "yevamot.json": "Yevamot",
  "ketubot.json": "Ketubot",
  "nedarim.json": "Nedarim",
  "nazir.json": "Nazir",
  "sotah.json": "Sotah",
  "gittin.json": "Gittin",
  "kiddushin.json": "Kiddushin",
  "bava-kamma.json": "Bava Kamma",
  "bava-metzia.json": "Bava Metzia",
  "bava-batra.json": "Bava Batra",
  "sanhedrin.json": "Sanhedrin",
  "makkot.json": "Makkot",
  "shevuot.json": "Shevuot",
  "avodah-zarah.json": "Avodah Zarah",
  "horayot.json": "Horayot",
  "zevachim.json": "Zevachim",
  "menachot.json": "Menachot",
  "chullin.json": "Chullin",
  "bekhorot.json": "Bekhorot",
  "arakhin.json": "Arakhin",
  "temurah.json": "Temurah",
  "keritot.json": "Keritot",
  "meilah.json": "Meilah",
  "tamid.json": "Tamid",
  "middot.json": "Middot",
  "kinnim.json": "Kinnim",
  "niddah.json": "Niddah"
};

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function cleanHtml(str = "") {
  return String(str)
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function fetchSefaria(ref, lang = "he") {
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}?lang=${lang}&context=0&commentary=0`;

  for (let attempt = 1; attempt <= 4; attempt++) {
    try {
      const res = await fetch(url);

      if (!res.ok) {
        console.log(`Erreur ${res.status} : ${ref}`);
        await delay(800 * attempt);
        continue;
      }

      return await res.json();
    } catch (e) {
      console.log(`Erreur réseau ${attempt}/4 : ${e.message}`);
      await delay(800 * attempt);
    }
  }

  return null;
}

function extractText(data, lang) {
  if (!data) return "";

  const raw = lang === "he"
    ? (data.he || data.heText || [])
    : (data.text || data.en || []);

  if (Array.isArray(raw)) {
    return raw
      .flat(Infinity)
      .filter(Boolean)
      .map(cleanHtml)
      .join(" ")
      .trim();
  }

  if (typeof raw === "string") {
    return cleanHtml(raw);
  }

  return "";
}

async function fetchCommentaryForMasechet(commentary, file) {
  const masechet = masechetMap[file];

  if (!masechet) {
    console.log(`Ignoré : ${file}`);
    return;
  }

  const srcPath = path.join(mergedDir, file);
  const outDir = path.join(outBase, commentary.slug);
  const outPath = path.join(outDir, file);

  fs.mkdirSync(outDir, { recursive: true });

  const talmud = JSON.parse(fs.readFileSync(srcPath, "utf8"));

  let output = fs.existsSync(outPath)
    ? JSON.parse(fs.readFileSync(outPath, "utf8"))
    : {
        masechet,
        file,
        commentary: commentary.title,
        dapim: []
      };

  const byDaf = new Map((output.dapim || []).map(d => [String(d.daf), d]));
  const dapim = Object.keys(talmud.dapim || {}).sort();

  console.log(`\n📘 ${masechet} — ${commentary.title}`);

  for (const daf of dapim) {
    let existing = byDaf.get(String(daf)) || {
      daf,
      comments: []
    };

    const alreadyHasText = (existing.comments || []).some(c => c.he || c.en);

    if (!alreadyHasText) {
      const ref = `${commentary.sefaria} on ${masechet} ${daf}`;

      const heData = await fetchSefaria(ref, "he");
      const enData = await fetchSefaria(ref, "en");

      const he = extractText(heData, "he");
      const en = extractText(enData, "en");

      existing.comments = [];

      if (he || en) {
        existing.comments.push({
          he,
          en,
          fr: ""
        });
      }

      await delay(180);
    }

    byDaf.set(String(daf), existing);

    output.dapim = Array.from(byDaf.values());
    fs.writeFileSync(outPath, JSON.stringify(output, null, 2), "utf8");

    console.log(`✓ ${masechet} ${daf} ${commentary.title} : ${existing.comments.length}`);
  }

  console.log(`✅ ${outPath}`);
}

async function main() {
  const files = fs.readdirSync(mergedDir)
    .filter(f => f.endsWith(".json"));

  for (const commentary of commentaries) {
    for (const file of files) {
      await fetchCommentaryForMasechet(commentary, file);
    }
  }

  console.log("\n✅ Commentaires Talmud terminés.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
