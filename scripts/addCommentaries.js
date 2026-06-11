import fs from "fs";
import path from "path";

const masechetSlug = process.argv[2] || "berakhot";
const filePath = path.join("public", "data", "merged", `${masechetSlug}.json`);

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchText(ref) {
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}`;
  const res = await fetch(url);

  if (!res.ok) {
    return { he: [], text: [] };
  }

  return await res.json();
}

async function main() {
  if (!fs.existsSync(filePath)) {
    console.error("Fichier introuvable :", filePath);
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const title = data.title;
  const dapim = Object.keys(data.dapim || {});

  for (const daf of dapim) {
    console.log("Commentaires :", title, daf);

    const rashi = await fetchText(`Rashi on ${title} ${daf}`);
    await sleep(250);

    const tosafot = await fetchText(`Tosafot on ${title} ${daf}`);
    await sleep(250);

    data.dapim[daf].rashi = rashi.he || [];
    data.dapim[daf].tosafot = tosafot.he || [];
  }

  fs.writeFileSync(filePath, JSON.stringify(data), "utf8");

  console.log("OK commentaires ajoutés :", filePath);
}

main();
