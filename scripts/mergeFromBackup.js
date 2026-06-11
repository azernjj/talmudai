import fs from "fs";
import path from "path";

const SRC = "/home/pi/talmud_old_json_backup";
const OUT = "public/data/merged";

fs.mkdirSync(OUT, { recursive: true });

const files = fs.readdirSync(SRC).filter(f => f.endsWith(".json"));
const groups = {};

for (const file of files) {
  const match = file.match(/^(.+)_([0-9]+[ab])\.json$/);
  if (!match) continue;

  const masechet = match[1];

  if (masechet.startsWith("Rashi_on_")) continue;
  if (masechet.startsWith("Tosafot_on_")) continue;

  const daf = match[2];

  if (!groups[masechet]) {
    groups[masechet] = {
      title: masechet.replaceAll("_", " "),
      dapim: {}
    };
  }

  const data = JSON.parse(fs.readFileSync(path.join(SRC, file), "utf8"));

  const he = data.he || [];
  const en = data.text || [];
  const max = Math.max(he.length, en.length);

  groups[masechet].dapim[daf] = {
    segments: Array.from({ length: max }, (_, i) => ({
      id: i + 1,
      he: he[i] || "",
      en: en[i] || "",
      fr: ""
    })),
    rashi: [],
    tosafot: []
  };
}

for (const [masechet, data] of Object.entries(groups)) {
  const filename = masechet.toLowerCase().replaceAll("_", "-") + ".json";
  fs.writeFileSync(path.join(OUT, filename), JSON.stringify(data), "utf8");
  console.log("OK", filename, Object.keys(data.dapim).length, "dapim");
}
