#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse, html, json, os, re, shutil, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from openai import OpenAI

VERSION = "6.0"
DEFAULT_FIELD = "etude_v6_fr"
DEFAULT_LOG = "logs/talmud_translation_v6.jsonl"

SYSTEM_PROMPT = """
Tu es un spécialiste de très haut niveau du Talmud Bavli, de l'hébreu
rabbinique, de l'araméen babylonien et des commentaires classiques.
Travaille sur UN SEUL segment et traduis directement depuis l'hébreu/araméen.

PRIORITÉS
1. Traduction française complète, fidèle, précise et naturelle.
2. Respect exact de la logique talmudique.
3. Explications brèves immédiatement après la portion traduite qu'elles éclairent.
4. Aucune invention de commentaire, source, opinion ou halakha.

TERMINOLOGIE
- אשמורה = « garde », jamais « veille ».
- אור, lorsqu'il signifie la lumière = « or (lumière) ».
- יום טוב = « Yom Tov ».
- Utilise « il pourrait », jamais « it pourrait ».

SORTIE
- traduction : 1 à 6 blocs {texte, explication}. Ne répète pas l'hébreu.
- rachi, tossefot : idée centrale, très concise, seulement si certaine.
- ritva, roch : apport distinct et certain seulement ; sinon chaîne vide.
- synthese : 2 à 4 phrases maximum.
- halakha : conséquence courte et vérifiable. Sinon écris exactement :
  « Aucune halakha pratique certaine ne découle directement de ce passage. »
- avertissements : uniquement les incertitudes réelles.

Si un commentaire n'est pas fourni et que tu n'es pas certain de son contenu,
laisse sa rubrique vide. Ne remplis jamais une rubrique pour la remplir.
Retourne uniquement le JSON conforme au schéma.
"""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["traduction","rachi","tossefot","ritva","roch","synthese","halakha","avertissements"],
    "properties": {
        "traduction": {
            "type": "array", "minItems": 1, "maxItems": 6,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["texte","explication"],
                "properties": {"texte":{"type":"string"},"explication":{"type":"string"}}
            }
        },
        "rachi":{"type":"string"}, "tossefot":{"type":"string"},
        "ritva":{"type":"string"}, "roch":{"type":"string"},
        "synthese":{"type":"string"}, "halakha":{"type":"string"},
        "avertissements":{"type":"array","maxItems":3,"items":{"type":"string"}}
    }
}

def now(): return datetime.now(timezone.utc).isoformat()

def load_json(path):
    with path.open(encoding="utf-8") as f: return json.load(f)

def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2); f.write("\n")
    os.replace(tmp, path)

def append_log(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def backup(path):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.stem}.before-v6-{stamp}{path.suffix}.bak")
    shutil.copy2(path, dest); return dest

def daf_key(value):
    m = re.fullmatch(r"\s*(\d+)\s*([abAB])?\s*", str(value))
    return (int(m.group(1)), 0 if (m.group(2) or "a").lower()=="a" else 1, str(value)) if m else (10**9,0,str(value))

def get_dapim(data):
    if isinstance(data, dict):
        for key in ("dapim","pages","dafim"):
            if isinstance(data.get(key), dict): return data[key]
        for value in data.values():
            try: return get_dapim(value)
            except LookupError: pass
    raise LookupError("Clé dapim/pages/dafim introuvable.")

def get_segments(page):
    if isinstance(page, list) and all(isinstance(x,dict) for x in page): return page
    if isinstance(page, dict):
        for key in ("segments","items","texts"):
            value = page.get(key)
            if isinstance(value,list) and all(isinstance(x,dict) for x in value): return value
    raise LookupError("Liste de segments introuvable.")

def original_text(segment):
    for key in ("he","hebrew","text_he","original","text","source","heb"):
        value = segment.get(key)
        if isinstance(value,str) and value.strip(): return value.strip()
    raise ValueError("Texte hébreu/araméen introuvable.")

def tractate_name(path, data):
    if isinstance(data,dict):
        for key in ("title","masekhet","tractate","name","slug"):
            value=data.get(key)
            if isinstance(value,str) and value.strip(): return value.strip()
    return path.stem.replace("-"," ").replace("_"," ").title()

def complete(segment, field):
    study=segment.get(field)
    blocks=study.get("traduction") if isinstance(study,dict) else None
    return isinstance(blocks,list) and bool(blocks) and all(isinstance(b,dict) and str(b.get("texte","")).strip() for b in blocks)

def output_text(response):
    direct=getattr(response,"output_text",None)
    if isinstance(direct,str) and direct.strip(): return direct.strip()
    pieces=[]
    for item in getattr(response,"output",[]) or []:
        for content in getattr(item,"content",[]) or []:
            text=getattr(content,"text",None)
            if isinstance(text,str): pieces.append(text)
            elif getattr(text,"value",None): pieces.append(text.value)
    return "\n".join(pieces).strip()

def parse_json(text):
    text=re.sub(r"^```(?:json)?\s*","",text.strip(),flags=re.I)
    text=re.sub(r"\s*```$","",text)
    try: result=json.loads(text)
    except json.JSONDecodeError:
        start,end=text.find("{"),text.rfind("}")
        if start<0 or end<=start: raise
        result=json.loads(text[start:end+1])
    if not isinstance(result,dict): raise ValueError("La réponse doit être un objet JSON.")
    return result

def usage(response):
    u=getattr(response,"usage",None)
    def read(*names):
        for name in names:
            value=getattr(u,name,None) if u is not None else None
            if isinstance(value,int): return value
            if isinstance(u,dict) and isinstance(u.get(name),int): return u[name]
        return 0
    inp,out=read("input_tokens","prompt_tokens"),read("output_tokens","completion_tokens")
    return {"input_tokens":inp,"output_tokens":out,"total_tokens":read("total_tokens") or inp+out}

def call_model(client, model, user_prompt, max_tokens, effort, retries):
    last=None
    for attempt in range(1,retries+1):
        try:
            params={"model":model,"input":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":user_prompt}],"max_output_tokens":max_tokens}
            if effort!="none": params["reasoning"]={"effort":effort}
            try:
                response=client.responses.create(**params,text={"format":{"type":"json_schema","name":"talmud_v6","strict":True,"schema":SCHEMA}})
            except Exception as structured_error:
                msg=str(structured_error).lower()
                if not any(x in msg for x in ("json_schema","text.format","unknown parameter","unsupported","invalid_request")): raise
                response=client.responses.create(**params)
            raw=output_text(response)
            if not raw: raise RuntimeError("Réponse API vide.")
            return parse_json(raw),usage(response)
        except Exception as exc:
            last=exc
            if attempt==retries: break
            delay=min(30,2**attempt)
            print(f"⚠️ Échec API {attempt}/{retries}: {exc}; nouvel essai dans {delay}s",file=sys.stderr)
            time.sleep(delay)
    raise last

def clean_result(result):
    blocks=result.get("traduction")
    if not isinstance(blocks,list) or not blocks: raise ValueError("Traduction absente.")
    clean=[]
    for block in blocks:
        if not isinstance(block,dict): continue
        text=str(block.get("texte","")).strip()
        explanation=str(block.get("explication","")).strip()
        if text: clean.append({"texte":text,"explication":explanation})
    if not clean: raise ValueError("Aucun bloc valide.")
    final={"traduction":clean}
    for key in ("rachi","tossefot","ritva","roch","synthese","halakha"):
        final[key]=str(result.get(key,"")).strip()
    warnings=result.get("avertissements")
    final["avertissements"]=[str(x).strip() for x in warnings if str(x).strip()][:3] if isinstance(warnings,list) else []
    if not final["halakha"]:
        final["halakha"]="Aucune halakha pratique certaine ne découle directement de ce passage."
    return final

def build_fr_html(study):
    parts=[]
    for block in study["traduction"]:
        t=html.escape(block["texte"],quote=False)
        e=html.escape(block["explication"],quote=False)
        parts.append(f"<b>{t}</b>{' '+e if e else ''}")
    return " ".join(parts)

def commentary_text(segment,names):
    for name in names:
        value=segment.get(name)
        if isinstance(value,str) and value.strip(): return value.strip()
        if isinstance(value,list):
            pieces=[]
            for item in value:
                if isinstance(item,str) and item.strip(): pieces.append(item.strip())
                elif isinstance(item,dict):
                    for key in ("he","text","comment","content"):
                        text=item.get(key)
                        if isinstance(text,str) and text.strip(): pieces.append(text.strip()); break
            if pieces: return "\n".join(pieces)
        if isinstance(value,dict):
            for key in ("he","text","comment","content"):
                text=value.get(key)
                if isinstance(text,str) and text.strip(): return text.strip()
    return ""

def prompt(reference, original, before, after, rashi, tosafot):
    return f"""RÉFÉRENCE
{reference}

SEGMENT À TRADUIRE
{original}

CONTEXTE AVANT — compréhension seulement
{before or "Non fourni."}

CONTEXTE APRÈS — compréhension seulement
{after or "Non fourni."}

RACHI FOURNI
{rashi or "Non fourni."}

TOSSEFOT FOURNIS
{tosafot or "Non fournis."}

Traduis uniquement le segment central. Appuie Rachi et Tossefot sur les textes
fournis lorsqu'ils existent. Retourne uniquement le JSON."""

def arguments():
    p=argparse.ArgumentParser(description="TALMUD AI — moteur V6")
    p.add_argument("--file",required=True)
    p.add_argument("--only-daf"); p.add_argument("--start-daf"); p.add_argument("--end-daf")
    p.add_argument("--start-segment",type=int,default=1); p.add_argument("--limit",type=int,default=0)
    p.add_argument("--model",default="gpt-5-nano")
    p.add_argument("--max-output-tokens",type=int,default=900)
    p.add_argument("--reasoning-effort",choices=("none","low","medium","high"),default="low")
    p.add_argument("--field",default=DEFAULT_FIELD); p.add_argument("--force",action="store_true")
    p.add_argument("--backup",action="store_true"); p.add_argument("--dry-run",action="store_true")
    p.add_argument("--retries",type=int,default=3); p.add_argument("--log",default=DEFAULT_LOG)
    return p.parse_args()

def main():
    args=arguments(); path=Path(args.file); log=Path(args.log)
    if not path.is_file(): print(f"❌ Fichier introuvable : {path}",file=sys.stderr); return 2
    if args.start_segment<1 or args.retries<1: print("❌ Paramètre numérique invalide.",file=sys.stderr); return 2
    if args.only_daf and (args.start_daf or args.end_daf):
        print("❌ Utilise soit --only-daf, soit --start-daf/--end-daf.",file=sys.stderr); return 2
    data=load_json(path); dapim=get_dapim(data); masekhet=tractate_name(path,data)
    if args.backup and not args.dry_run: print(f"🛟 Sauvegarde : {backup(path)}")
    selected=[]; start=daf_key(args.start_daf) if args.start_daf else None; end=daf_key(args.end_daf) if args.end_daf else None
    for daf in sorted(dapim,key=daf_key):
        key=daf_key(daf)
        if args.only_daf and daf!=args.only_daf: continue
        if start and key<start: continue
        if end and key>end: continue
        segs=get_segments(dapim[daf])
        for i,seg in enumerate(segs):
            if args.only_daf and i+1<args.start_segment: continue
            if not args.force and complete(seg,args.field): continue
            selected.append((daf,i,seg,segs))
            if args.limit and len(selected)>=args.limit: break
        if args.limit and len(selected)>=args.limit: break
    print(f"📖 Fichier : {path}\n   Traité : {masekhet}\n   Version : {VERSION}\n   Modèle : {args.model}\n   Sortie max : {args.max_output_tokens}\n   Segments : {len(selected)}")
    if args.dry_run:
        for daf,i,*_ in selected: print(f"- {masekhet} {daf}:{i+1}")
        return 0
    if not selected: print("✅ Aucun segment à traiter."); return 0
    if not os.environ.get("OPENAI_API_KEY"): print("❌ OPENAI_API_KEY n'est pas définie.",file=sys.stderr); return 2
    client=OpenAI(); totals={"input_tokens":0,"output_tokens":0,"total_tokens":0}; ok=failed=0
    for pos,(daf,index,segment,segs) in enumerate(selected,1):
        reference=f"{masekhet} {daf}:{index+1}"; print(f"\n🔎 {reference} ({pos}/{len(selected)})")
        try:
            original=original_text(segment)
            before=original_text(segs[index-1]) if index>0 else ""
            after=original_text(segs[index+1]) if index+1<len(segs) else ""
            rashi=commentary_text(segment,("rashi","Rashi","rachi","Rachi"))
            tosafot=commentary_text(segment,("tosafot","Tosafot","tossefot","Tossefot"))
            result,use=call_model(client,args.model,prompt(reference,original,before,after,rashi,tosafot),args.max_output_tokens,args.reasoning_effort,args.retries)
            final=clean_result(result)
            segment[args.field]=final
            segment["fr"]=build_fr_html(final)
            segment["fr_plain"]=" ".join(b["texte"] for b in final["traduction"]).strip()
            segment["translation_meta_v6"]={"script_version":VERSION,"translated_at":now(),"model":args.model,"max_output_tokens":args.max_output_tokens,"usage":use}
            save_json(path,data)
            append_log(log,{"timestamp":now(),"status":"success","file":str(path),"reference":reference,"model":args.model,"usage":use})
            for k in totals: totals[k]+=use[k]
            ok+=1
            print(f"✅ Sauvegardé — {use['input_tokens']} entrée, {use['output_tokens']} sortie, {use['total_tokens']} total")
        except KeyboardInterrupt:
            print("\n🛑 Arrêt demandé. Tout ce qui était terminé est sauvegardé."); break
        except Exception as exc:
            failed+=1; print(f"❌ {reference} : {exc}",file=sys.stderr)
            append_log(log,{"timestamp":now(),"status":"error","file":str(path),"reference":reference,"error":str(exc),"traceback":traceback.format_exc()})
    print("\n"+"="*60)
    print(f"✅ Réussites : {ok}\n❌ Échecs : {failed}\n📥 Entrée : {totals['input_tokens']}\n📤 Sortie : {totals['output_tokens']}\n🧮 Total : {totals['total_tokens']}\n💾 Fichier : {path}\n📝 Journal : {log}")
    return 0 if failed==0 else 1

if __name__=="__main__":
    raise SystemExit(main())
