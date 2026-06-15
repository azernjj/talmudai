import fs from "fs";
import path from "path";

const inputDir = "public/data/merged";
const outputDir = "public/data/search";

fs.mkdirSync(outputDir, { recursive: true });

function cleanText(s = "") {
  return String(s)
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

for (const file of fs.readdirSync(inputDir)) {
  if (!file.endsWith(".json")) continue;

  const fullPath = path.join(inputDir, file);
  const data = JSON.parse(fs.readFileSync(fullPath, "utf8"));
  const title = data.title || file.replace(".json", "");

  const index = [];

  for (const [daf, dafData] of Object.entries(data.dapim || {})) {
    for (const type of ["segments", "rashi", "tosafot"]) {
      const arr = dafData[type] || [];

      arr.forEach((seg, i) => {
        const text = cleanText([
          seg.he || "",
          seg.en || "",
          seg.fr || ""
        ].join(" "));

        if (!text) return;

        index.push({
          masechet: title,
          file,
          daf,
          type,
          id: seg.id || i + 1,
          text
        });
      });
    }
  }

  const outFile = path.join(outputDir, file.replace(".json", ".search.json"));
  fs.writeFileSync(outFile, JSON.stringify(index), "utf8");

  const sizeMb = fs.statSync(outFile).size / 1024 / 1024;
  console.log(`${outFile} : ${index.length} entrées, ${sizeMb.toFixed(2)} MB`);
}

console.log("Index par traité terminé.");
