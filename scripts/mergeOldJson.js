import fs from "fs";
import path from "path";

const SOURCE = "/home/pi/talmud_old_json_backup";
const OUT = "/home/pi/talmud-ai-vercel/public/data/bavli";

const masechtot = [
  "Berakhot",
  "Shabbat",
  "Eruvin",
  "Pesachim",
  "Yoma",
  "Sukkah",
  "Beitzah",
  "Rosh_Hashanah",
  "Taanit",
  "Megillah",
  "Moed_Katan",
  "Chagigah",
  "Yevamot",
  "Ketubot",
  "Nedarim",
  "Nazir",
  "Sotah",
  "Gittin",
  "Kiddushin",
  "Bava_Kamma",
  "Bava_Metzia",
  "Bava_Batra",
  "Sanhedrin",
  "Makkot",
  "Shevuot",
  "Avodah_Zarah",
  "Horayot",
  "Zevachim",
  "Menachot",
  "Chullin",
  "Bekhorot",
  "Arakhin",
  "Temurah",
  "Keritot",
  "Meilah",
  "Tamid",
  "Middot",
  "Kinnim",
  "Niddah"
];

function slug(name) {
  return name.toLowerCase().replaceAll("_", "-");
}

function extractDaf(filename, masechet) {
  return filename
    .replace(masechet + "_", "")
    .replace(".json", "");
}

function normalizePage(data) {
  const he = data.he || [];
  const en = data.text || [];
  const max = Math.max(he.length, en.length);

  return {
    segments: Array.from({ length: max }, (_, i) => ({
      id: i + 1,
      he: he[i] || "",
      en: en[i] || "",
      fr: ""
    }))
  };
}

fs.mkdirSync(OUT, { recursive: true });

for (const masechet of masechtot) {
  const files = fs
    .readdirSync(SOURCE)
    .filter(f => f.startsWith(masechet + "_") && f.endsWith(".json"));

  if (!files.length) {
    console.log("Aucun fichier :", masechet);
    continue;
  }

  const output = {
    title: masechet.replaceAll("_", " "),
    dapim: {}
  };

  for (const file of files) {
    try {
      const daf = extractDaf(file, masechet);
      const fullPath = path.join(SOURCE, file);
      const raw = fs.readFileSync(fullPath, "utf8");
      const data = JSON.parse(raw);

      output.dapim[daf] = normalizePage(data);
    } catch (e) {
      console.log("Erreur fichier :", file, e.message);
    }
  }

  const outFile = path.join(OUT, slug(masechet) + ".json");
  fs.writeFileSync(outFile, JSON.stringify(output), "utf8");

  console.log(
    "OK",
    masechet,
    Object.keys(output.dapim).length,
    "dapim →",
    outFile
  );
}
