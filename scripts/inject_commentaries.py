import json

MERGED  = "/home/pi/talmud-ai-vercel/public/data/merged/berakhot.json"
MERGED2 = "/home/pi/talmud-ai-vercel/dist/data/merged/berakhot.json"
ROSH    = "/home/pi/talmud-ai-vercel/public/data/commentaries/rosh/berakhot.json"
RITVA   = "/home/pi/talmud-ai-vercel/public/data/commentaries/ritva/berakhot.json"

with open(MERGED, encoding="utf-8") as f:
    merged = json.load(f)
with open(ROSH, encoding="utf-8") as f:
    rosh = json.load(f)
with open(RITVA, encoding="utf-8") as f:
    ritva = json.load(f)

# Indexer Rosh et Ritva par daf
rosh_index  = {d["daf"]: d["comments"] for d in rosh["dapim"]}
ritva_index = {d["daf"]: d["comments"] for d in ritva["dapim"]}

count_rosh = 0
count_ritva = 0

for daf in merged["dapim"]:
    # Injecter Rosh
    if daf in rosh_index:
        merged["dapim"][daf]["rosh"] = rosh_index[daf]
        count_rosh += 1
    else:
        merged["dapim"][daf]["rosh"] = []

    # Injecter Ritva
    if daf in ritva_index:
        merged["dapim"][daf]["ritva"] = ritva_index[daf]
        count_ritva += 1
    else:
        merged["dapim"][daf]["ritva"] = []

# Remplacer ashmoura par garde dans tout le fichier
content = json.dumps(merged, ensure_ascii=False, indent=2)
content = content.replace("ashmoura", "garde")
merged = json.loads(content)

# Sauvegarder
for path in [MERGED, MERGED2]:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

print("Rosh injecte pour " + str(count_rosh) + " dapim")
print("Ritva injecte pour " + str(count_ritva) + " dapim")
print("ashmoura remplace par garde")
print("Termine !")
