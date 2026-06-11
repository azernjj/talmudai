const fs = require("fs");
const path = require("path");

const masechet = process.argv[2] || "Berakhot";

const info = {
  Berakhot: { title: "Berakhot", last: 64, slug: "berakhot" },
  Shabbat: { title: "Shabbat", last: 157, slug: "shabbat" }
};

if (!info[masechet]) {
  console.error("Traité non configuré :", masechet);
  process.exit(1);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function getText(ref) {
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${ref} : ${res.status}`);
  return await res.json();
}

async function main() {
  const cfg = info[masechet];
  const output = {
    title: cfg.title,
    dapim: {}
  };

  for (let i = 2; i <= cfg.last; i++) {
    for (const side of ["a", "b"]) {
      const daf = `${i}${side}`;
      const ref = `${cfg.title} ${daf}`;

      try {
        console.log("Import", ref);
        const data = await getText(ref);

        const he = data.he || [];
        const en = data.text || [];
        const max = Math.max(he.length, en.length);

        output.dapim[daf] = {
          segments: Array.from({ length: max }, (_, idx) => ({
            id: idx + 1,
            he: he[idx] || "",
            en: en[idx] || "",
            fr: ""
          })),
          rashi: [],
          tosafot: []
        };

        await sleep(250);
      } catch (e) {
        console.log("Ignoré", ref, e.message);
      }
    }
  }

  const outDir = path.join(process.cwd(), "public", "data", "bavli");
  fs.mkdirSync(outDir, { recursive: true });

  const outFile = path.join(outDir, `${cfg.slug}.json`);
  fs.writeFileSync(outFile, JSON.stringify(output, null, 2), "utf8");

  console.log("Fichier créé :", outFile);
}

main();
