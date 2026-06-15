import fs from "fs";
import path from "path";

const inputDir = "public/data/merged";
const outputFile = "public/data/search-index.json";

const index = [];

for (const file of fs.readdirSync(inputDir)) {
  if (!file.endsWith(".json")) continue;

  const fullPath = path.join(inputDir, file);
  const data = JSON.parse(fs.readFileSync(fullPath, "utf8"));
  const title = data.title || file.replace(".json", "");

  for (const [daf, dafData] of Object.entries(data.dapim || {})) {
    for (const type of ["segments", "rashi", "tosafot"]) {
      const arr = dafData[type] || [];

      arr.forEach((seg, i) => {
        index.push({
          masechet: title,
          file,
          daf,
          type,
          id: seg.id || i + 1,
          he: seg.he || "",
          en: seg.en || "",
          fr: seg.fr || ""
        });
      });
    }
  }
}

fs.writeFileSync(outputFile, JSON.stringify(index, null, 2), "utf8");

console.log(`Index créé : ${outputFile}`);
console.log(`Entrées : ${index.length}`);
