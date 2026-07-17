cat > /home/pi/translate_berakhot.py << 'PYEOF'
import urllib.request, json, time, os

MERGED     = "/home/pi/talmud-ai-vercel/dist/data/merged/berakhot.json"
PUBLIC     = "/home/pi/talmud-ai-vercel/public/data/merged/berakhot.json"
CHECKPOINT = "/home/pi/translate_checkpoint.json"
API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM = """Tu es un expert talmudiste francophone avec une maîtrise parfaite de l'hébreu rabbinique et de l'araméen babylonien talmudique.

Traduis ce segment du Talmud Babylonien (Berakhot) DIRECTEMENT depuis l'hébreu/araméen vers le français, sans passer par l'anglais.

Règles :
- Traduction fluide et naturelle en français
- Termes techniques en hébreu translittéré avec courte explication : ex. terouma (offrande sacrerdotale)
- Noms de rabbins translittérés : Rabbi Yohanan, Rav Hisda...
- Citations bibliques traduites avec référence : (Psaumes 1:1)
- Retourne UNIQUEMENT la traduction, rien d'autre"""

def translate(he, en=""):
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 800,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": f"Traduis en français :\n\n{he}"}]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    return result["content"][0]["text"].strip()

def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {}

def save_checkpoint(done):
    with open(CHECKPOINT, "w") as f:
        json.dump(done, f)

with open(MERGED, encoding="utf-8") as f:
    data = json.load(f)

done = load_checkpoint()
total = sum(len(data["dapim"][d]["segments"]) for d in data["dapim"])
count = 0
errors = 0

print(f"Total segments: {total}")
print(f"Deja traduits: {len(done)}")
print("Demarrage...\n")

for daf in sorted(data["dapim"].keys()):
    for seg in data["dapim"][daf]["segments"]:
        count += 1
        key = f"{daf}_{seg['id']}"

        if key in done:
            seg["fr"] = done[key]
            continue

        he = seg.get("he", "").strip()
        if not he:
            continue

        try:
            fr = translate(he)
            seg["fr"] = fr
            done[key] = fr
            print(f"[{count}/{total}] {daf} seg.{seg['id']}")
            print(f"  HE: {he[:70]}")
            print(f"  FR: {fr[:70]}\n")

            if count % 20 == 0:
                save_checkpoint(done)
                with open(MERGED, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                with open(PUBLIC, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"  >>> Checkpoint {count}/{total} sauvegarde\n")

            time.sleep(0.3)

        except Exception as e:
            errors += 1
            print(f"[{count}/{total}] ERREUR {daf} seg.{seg['id']}: {e}")

save_checkpoint(done)
with open(MERGED, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
with open(PUBLIC, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\nTermine ! Traduits: {len(done)} Erreurs: {errors}")
PYEOF
