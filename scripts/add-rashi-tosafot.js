import fs from "fs";
import path from "path";

const dir = "public/data/merged";

for (const file of fs.readdirSync(dir)) {
  if (!file.endsWith(".json")) continue;

  const fullPath = path.join(dir, file);
  const data = JSON.parse(fs.readFileSync(fullPath, "utf8"));

  if (!data.dapim) continue;

  let changed = false;

  for (const daf of Object.keys(data.dapim)) {
    if (!Array.isArray(data.dapim[daf].segments)) {
      data.dapim[daf].segments = [];
      changed = true;
    }

    if (!Array.isArray(data.dapim[daf].rashi)) {
      data.dapim[daf].rashi = [];
      changed = true;
    }

    if (!Array.isArray(data.dapim[daf].tosafot)) {
      data.dapim[daf].tosafot = [];
      changed = true;
    }
  }

  if (changed) {
    fs.writeFileSync(fullPath, JSON.stringify(data, null, 2), "utf8");
    console.log("Corrigé :", file);
  }
}

console.log("Terminé.");
