import fs from "fs";
import path from "path";

const mergedPath = "public/data/merged/berakhot.json";
const sourceDir = "/home/pi/talmud_old_json_backup";

const data = JSON.parse(fs.readFileSync(mergedPath, "utf8"));

function loadCommentary(fileName) {
  const filePath = path.join(sourceDir, fileName);

  if (!fs.existsSync(filePath)) {
    return [];
  }

  const json = JSON.parse(fs.readFileSync(filePath, "utf8"));
  return json.he || [];
}

if (data.dapim["2a"]) {
  data.dapim["2a"].rashi = loadCommentary("Rashi_on_Berakhot_2a.json");
  data.dapim["2a"].tosafot = loadCommentary("Tosafot_on_Berakhot_2a.json");
}

fs.writeFileSync(mergedPath, JSON.stringify(data), "utf8");

console.log("Rashi/Tosafot restaurés pour Berakhot 2a");
