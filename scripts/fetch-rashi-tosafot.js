import fs from "fs";
import path from "path";

const dir = "public/data/merged";

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

function cleanHtml(str = "") {
  return String(str)
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function fetchText(ref) {
  const url = `https://www.sefaria.org/api/v3/texts/${encodeURIComponent(ref)}?version=hebrew|Vilna%20Edition`;
  const res = await fetch(url);
  if (!res.ok) return [];
  const data = await res.json();

  const text =
    data?.versions?.[0]?.text ||
    data?.text ||
    [];

  if (Array.isArray(text)) return text.flat(Infinity).filter(Boolean);
  if (typeof text === "string") return [text];
  return [];
}

async function processFile(file) {
  const masechet = masechetMap[file];
  if (!masechet) {
    console.log("Ignoré :", file);
    return;
  }

  const fullPath = path.join(dir, file);
  const data = JSON.parse(fs.readFileSync(fullPath, "utf8"));

  let changed = false;

  for (const daf of Object.keys(data.dapim || {})) {
    const page = data.dapim[daf];

    page.rashi = Array.isArray(page.rashi) ? page.rashi : [];
    page.tosafot = Array.isArray(page.tosafot) ? page.tosafot : [];

    if (page.rashi.length === 0) {
      const rashiRef = `Rashi on ${masechet} ${daf}`;
      const rashi = await fetchText(rashiRef);

      page.rashi = rashi.map((he, i) => ({
        id: i + 1,
        he: cleanHtml(he),
        en: "",
        fr: ""
      }));

      if (page.rashi.length) changed = true;
    }

    if (page.tosafot.length === 0) {
      const tosafotRef = `Tosafot on ${masechet} ${daf}`;
      const tosafot = await fetchText(tosafotRef);

      page.tosafot = tosafot.map((he, i) => ({
        id: i + 1,
        he: cleanHtml(he),
        en: "",
        fr: ""
      }));

      if (page.tosafot.length) changed = true;
    }

    console.log(`${file} ${daf} : Rachi ${page.rashi.length}, Tossefot ${page.tosafot.length}`);

    await new Promise(r => setTimeout(r, 250));
  }

  if (changed) {
    fs.writeFileSync(fullPath, JSON.stringify(data, null, 2), "utf8");
    console.log("Sauvegardé :", file);
  }
}

for (const file of fs.readdirSync(dir)) {
  if (file.endsWith(".json")) {
    await processFile(file);
  }
}

console.log("Terminé.");
