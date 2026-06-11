import fs from "fs";
import path from "path";

const masechetSlug = process.argv[2] || "berakhot";

const mergedPath = path.join("public", "data", "merged", `${masechetSlug}.json`);
const frPath = path.join("public", "data", "translations", "fr", `${masechetSlug}.json`);

if (!fs.existsSync(mergedPath)) {
  console.error("Fichier merged introuvable :", mergedPath);
  process.exit(1);
}

if (!fs.existsSync(frPath)) {
  console.error("Fichier français introuvable :", frPath);
  process.exit(1);
}

const merged = JSON.parse(fs.readFileSync(mergedPath, "utf8"));
const fr = JSON.parse(fs.readFileSync(frPath, "utf8"));

for (const [daf, dafData] of Object.entries(fr.dapim || {})) {
  if (!merged.dapim[daf]) {
    console.log("Daf absent dans merged :", daf);
    continue;
  }

  const translations = dafData.segments || {};

  for (const [segmentId, text] of Object.entries(translations)) {
    const index = Number(segmentId) - 1;

    if (merged.dapim[daf].segments[index]) {
      merged.dapim[daf].segments[index].fr = text;
    }
  }
}

fs.writeFileSync(mergedPath, JSON.stringify(merged), "utf8");

console.log("Français appliqué :", masechetSlug);
