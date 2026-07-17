import urllib.request, json, time, os

MERGED     = "/home/pi/talmud-ai-vercel/dist/data/merged/berakhot.json"
PUBLIC_M   = "/home/pi/talmud-ai-vercel/public/data/merged/berakhot.json"
ROSH_D     = "/home/pi/talmud-ai-vercel/dist/data/commentaries/rosh/berakhot.json"
ROSH_P     = "/home/pi/talmud-ai-vercel/public/data/commentaries/rosh/berakhot.json"
RITVA_D    = "/home/pi/talmud-ai-vercel/dist/data/commentaries/ritva/berakhot.json"
RITVA_P    = "/home/pi/talmud-ai-vercel/public/data/commentaries/ritva/berakhot.json"
CHECKPOINT = "/home/pi/translate_final_checkpoint.json"
API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM = "Tu es un maitre de la Halakha et de la Guemara. Traduis directement depuis l hebreu/arameen vers le francais rigoureux. Termes techniques en hebreu translittere : terouma, kohanim, tanna, amora, ashmoura, baraita. Noms de rabbins translitteres. Aucune balise HTML. Reponds UNIQUEMENT avec le JSON demande."

def api_call(items, label):
    if not items:
        return []
    prompt = "Traduis en francais ces " + label + " (hebreu/arameen -> francais).\n"
    prompt += "Reponds UNIQUEMENT avec ce JSON : {\"result\": [\"trad1\", \"trad2\", ...]}\n\n"
    for i, he in enumerate(items):
        prompt += str(i) + ": " + he + "\n"
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 4000,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json", "x-api-key": API_KEY, "anthropic-version": "2023-06-01"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        text = json.loads(r.read())["content"][0]["text"].strip()
    start = text.find('{')
    end = text.rfind('}') + 1
    if start >= 0 and end > start:
        parsed = json.loads(text[start:end])
        return parsed.get("result", [])
    return []

def sort_daf(d):
    n = int(''.join(filter(str.isdigit, d)))
    s = 0 if d.endswith('a') else 1
    return (n, s)

def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {}

def save_checkpoint(done):
    with open(CHECKPOINT, "w") as f:
        json.dump(done, f)

def save_files(merged, rosh, ritva):
    for path, obj in [(MERGED, merged), (PUBLIC_M, merged), (ROSH_D, rosh), (ROSH_P, rosh), (RITVA_D, ritva), (RITVA_P, ritva)]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

# Chargement
with open(MERGED, encoding="utf-8") as f:
    merged = json.load(f)
with open(ROSH_D, encoding="utf-8") as f:
    rosh = json.load(f)
with open(RITVA_D, encoding="utf-8") as f:
    ritva = json.load(f)

done = load_checkpoint()
dapim = sorted(merged["dapim"].keys(), key=sort_daf)
total = len(dapim)
count = 0
errors = 0

print("Total dapim: " + str(total))
print("Deja faits: " + str(len(done)))

for daf in dapim:
    if daf in done:
        print("[SKIP] " + daf)
        continue

    count += 1
    print("[" + str(count) + "/" + str(total) + "] " + daf)

    daf_data = merged["dapim"][daf]
    segments = daf_data.get("segments", [])
    rashi_items = daf_data.get("rashi", [])
    tosafot_items = daf_data.get("tosafot", [])
    rosh_daf = next((d for d in rosh["dapim"] if d["daf"] == daf), None)
    ritva_daf = next((d for d in ritva["dapim"] if d["daf"] == daf), None)

    try:
        # APPEL 1 : segments Guemara non traduits
        segs_a_traduire = [(i, seg) for i, seg in enumerate(segments)
                           if not seg.get("translation_meta", {}).get("engine")]
        if segs_a_traduire:
            he_list = [seg.get("he", "") for _, seg in segs_a_traduire]
            print("  segments(" + str(len(he_list)) + ")...")
            trad = api_call(he_list, "segments de Guemara Berakhot " + daf)
            for j, (i, seg) in enumerate(segs_a_traduire):
                if j < len(trad) and trad[j]:
                    seg["fr"] = trad[j]
                    seg["translation_meta"] = {"engine": "claude-sonnet-4-6", "source": "hebrew_aramaic_direct"}
            print("  -> " + str(len(trad)) + " traduits")
            time.sleep(2)

        # APPEL 2 : Rachi
        rashi_he = []
        for r in rashi_items:
            he = r if isinstance(r, str) else r.get("he", "")
            rashi_he.append(he)
        if rashi_he:
            print("  rachi(" + str(len(rashi_he)) + ")...")
            trad_r = api_call(rashi_he, "commentaires de Rachi Berakhot " + daf)
            new_rashi = []
            for i, r in enumerate(rashi_items):
                he = r if isinstance(r, str) else r.get("he", "")
                fr = trad_r[i] if i < len(trad_r) else ""
                new_rashi.append({"he": he, "fr": fr})
            daf_data["rashi"] = new_rashi
            print("  -> " + str(len(trad_r)) + " traduits")
            time.sleep(2)

        # APPEL 3 : Tossafot
        tosafot_he = []
        for t in tosafot_items:
            he = t if isinstance(t, str) else t.get("he", "")
            tosafot_he.append(he)
        if tosafot_he:
            print("  tosafot(" + str(len(tosafot_he)) + ")...")
            trad_t = api_call(tosafot_he, "commentaires de Tossafot Berakhot " + daf)
            new_tosafot = []
            for i, t in enumerate(tosafot_items):
                he = t if isinstance(t, str) else t.get("he", "")
                fr = trad_t[i] if i < len(trad_t) else ""
                new_tosafot.append({"he": he, "fr": fr})
            daf_data["tosafot"] = new_tosafot
            print("  -> " + str(len(trad_t)) + " traduits")
            time.sleep(2)

        # APPEL 4 : Rosh
        if rosh_daf:
            rosh_he = [c.get("he", "") for c in rosh_daf.get("comments", []) if c.get("he")]
            if rosh_he:
                print("  rosh(" + str(len(rosh_he)) + ")...")
                trad_ro = api_call(rosh_he, "commentaires du Rosh Berakhot " + daf)
                for i, c in enumerate(rosh_daf.get("comments", [])):
                    if i < len(trad_ro):
                        c["fr"] = trad_ro[i]
                print("  -> " + str(len(trad_ro)) + " traduits")
                time.sleep(2)

        # APPEL 5 : Ritva
        if ritva_daf:
            ritva_he = [c.get("he", "") for c in ritva_daf.get("comments", []) if c.get("he")]
            if ritva_he:
                print("  ritva(" + str(len(ritva_he)) + ")...")
                trad_ri = api_call(ritva_he, "commentaires du Ritva Berakhot " + daf)
                for i, c in enumerate(ritva_daf.get("comments", [])):
                    if i < len(trad_ri):
                        c["fr"] = trad_ri[i]
                print("  -> " + str(len(trad_ri)) + " traduits")
                time.sleep(2)

        done[daf] = True
        save_checkpoint(done)
        save_files(merged, rosh, ritva)
        print("  [OK] " + daf)

    except Exception as e:
        errors += 1
        print("  ERREUR " + daf + ": " + str(e))
        time.sleep(10)

save_files(merged, rosh, ritva)
print("\nTermine ! Dapim: " + str(count) + " Erreurs: " + str(errors))
