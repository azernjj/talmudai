#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, json, os, random, shutil, sys, tempfile, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from openai import OpenAI

SYSTEM_PROMPT = '''Tu es un talmid hakham spécialiste de la Michna et de l'hébreu rabbinique.
Pour la Michna fournie, produis seulement :
1. une traduction française fidèle, complète et naturelle, directement depuis l'hébreu ;
2. jusqu'à cinq explications brèves de Méfarchim classiques réellement utiles, en français.

Règles : ne traduis jamais depuis l'anglais ; n'ajoute rien à la traduction ; respecte le vocabulaire traditionnel ; conserve Chabbat, Yom Tov, Michna, Guemara, halakha, mitsva, terouma, maasser, Chemita et peah. יום טוב = Yom Tov, jamais festival ou jour de fête. הָאַשְׁמוּרָה = la garde, jamais veille ou ashmoura. אוֹר = lumière, clarté ou jour selon le contexte, jamais ou.

Méfarchim : privilégie Bartenoura, Rambam sur la Michna, Tossafot Yom Tov et Tiféret Israël. Inclue Rachi, Tossafot ou Ramban uniquement lorsqu'un commentaire pertinent et identifiable éclaire directement cette Michna. N'invente jamais une opinion ni une référence. En cas de doute, omets le commentaire.
Retourne uniquement le JSON demandé.'''

SCHEMA = {
  'type':'object','additionalProperties':False,
  'properties':{
    'traduction_fr':{'type':'string'},
    'mefarshim':{'type':'array','maxItems':5,'items':{
      'type':'object','additionalProperties':False,
      'properties':{
        'auteur':{'type':'string'},
        'reference':{'type':'string'},
        'explication_fr':{'type':'string'}
      },
      'required':['auteur','reference','explication_fr']
    }},
    'incertitudes':{'type':'array','maxItems':3,'items':{'type':'string'}}
  },
  'required':['traduction_fr','mefarshim','incertitudes']
}

@dataclass
class Mishnah:
    node: dict[str, Any]
    path: str
    ref: str
    he: str

def txt(v: Any) -> str:
    if v is None: return ''
    if isinstance(v,str): return v.strip()
    if isinstance(v,list): return '\n'.join(txt(x) for x in v if txt(x))
    return str(v).strip()

def first(d: dict[str,Any], keys: tuple[str,...]) -> Any:
    for k in keys:
        v=d.get(k)
        if v not in (None,'',[],{}): return v
    return None

def walk(v: Any, path: str='$') -> Iterator[Mishnah]:
    if isinstance(v,dict):
        he=txt(first(v,('he','hebrew','text_he','heText')))
        if he:
            ref=txt(first(v,('ref','reference','id','title'))) or path
            yield Mishnah(v,path,ref,he)
        for k,c in v.items(): yield from walk(c,f'{path}.{k}')