import { state } from '../state.js'
import { cleanText, escapeHtml } from './utils.js'
export function openDictionary(initialSearch=''){
 document.querySelector('#dictionaryPanel').classList.remove('hidden'); document.querySelector('#dictOverlay').classList.remove('hidden')
 const input=document.querySelector('#dictSearch'); input.value=initialSearch||''; input.focus(); input.select()
 if(!state.dictionaryLoaded) loadDictionary(); else renderDictionaryResults()
}
export function closeDictionary(){document.querySelector('#dictionaryPanel').classList.add('hidden');document.querySelector('#dictOverlay').classList.add('hidden')}
export async function loadDictionary(){
 const status=document.querySelector('#dictStatus'); status.textContent='Chargement du dictionnaire...'
 const paths=['/data/dictionary/dictionary.json','/dictionary/dictionary.json','/data/dictionnaire/dictionary.json','/data/dictionary.json','/dictionary.json']
 let lastError=''
 for(const url of paths){try{const res=await fetch(url,{cache:'no-store'}); if(!res.ok){lastError=`${url} : ${res.status}`; continue} const raw=await res.json(); state.dictionaryItems=normalizeDictionaryJson(raw); state.dictionaryLoaded=true; status.textContent=`${state.dictionaryItems.length} entrées chargées.`; renderDictionaryResults(); return}catch(e){lastError=`${url} : ${e.message}`}}
 status.textContent='Dictionnaire introuvable. Dernier essai : '+lastError
}
function normalizeDictionaryJson(raw){
 const items=[]
 if(Array.isArray(raw)){raw.forEach(value=>{if(value&&typeof value==='object'){const term=value.term||value.aramic||value.he||value.hebrew||value.word||'';items.push({term:cleanText(term),aramic:cleanText(value.aramic||value.hebrew||value.he||term),fr:cleanText(value.fr||value.french||value.traduction||''),en:cleanText(value.en||value.english||''),category:value.category||'Dictionnaire'})}});return mergeDictionaryItems(items)}
 for(const [category,entries] of Object.entries(raw||{})){if(!entries||typeof entries!=='object')continue;for(const [term,value] of Object.entries(entries)){const parsed=parseDictionaryValue(value,category);items.push({term:cleanText(term),aramic:cleanText(parsed.aramic||term),fr:cleanText(parsed.fr),en:cleanText(parsed.en),category})}}
 return mergeDictionaryItems(items)
}
function isEnglishCategory(category=''){const c=String(category).toLowerCase();return c==='english'||c.includes('eng')}
function parseDictionaryValue(value,category=''){
 const english=isEnglishCategory(category)
 if(Array.isArray(value)) return {aramic:value[0]||'',fr:english?'':(value[2]||value[1]||''),en:english?(value[2]||value[1]||''):(value[1]||'')}
 if(value&&typeof value==='object') return {aramic:value.aramic||value.hebrew||value.he||value.term||'',fr:english?'':(value.fr||value.french||value.traduction||value.translation||''),en:value.en||value.english||(english?value.translation||'':'')}
 if(typeof value==='string'){const s=value.trim();try{const parsed=JSON.parse(s);if(Array.isArray(parsed))return{aramic:parsed[0]||'',fr:english?'':(parsed[2]||parsed[1]||''),en:english?(parsed[2]||parsed[1]||''):(parsed[1]||'')}}catch{} return {aramic:'',fr:english?'':s,en:english?s:''}}
 return {aramic:'',fr:'',en:''}
}
function mergeDictionaryItems(items){const map=new Map();for(const item of items){const key=item.term||item.aramic;if(!key)continue;if(!map.has(key))map.set(key,item);else{const old=map.get(key);map.set(key,{...old,aramic:old.aramic||item.aramic,fr:old.fr||item.fr,en:old.en||item.en,category:old.category||item.category})}}return Array.from(map.values())}
export function renderDictionaryResults(){
 const q=cleanText(document.querySelector('#dictSearch').value).toLowerCase(); const box=document.querySelector('#dictResults'); const status=document.querySelector('#dictStatus'); box.innerHTML=''
 if(!q){status.textContent=state.dictionaryLoaded?`${state.dictionaryItems.length} entrées chargées. Écris un mot.`:status.textContent; return}
 const exact=[],starts=[],contains=[]
 for(const item of state.dictionaryItems){const term=cleanText(item.term).toLowerCase(), aramic=cleanText(item.aramic).toLowerCase(), fr=cleanText(item.fr).toLowerCase(), en=cleanText(item.en).toLowerCase(); if(term===q||aramic===q) exact.push(item); else if(term.startsWith(q)||aramic.startsWith(q)) starts.push(item); else if(fr.includes(q)||en.includes(q)) contains.push(item)}
 const results=exact.length?exact:[...starts,...contains].slice(0,80); status.textContent=`${results.length} résultat(s).`
 if(!results.length){box.innerHTML='<div class="dictEmpty">Aucune traduction trouvée.</div>'; return}
 box.innerHTML=results.map(item=>`<div class="dictCard"><div class="dictTerm">${escapeHtml(item.aramic||item.term)}</div>${item.term&&item.term!==item.aramic?`<div><b>Entrée :</b> ${escapeHtml(item.term)}</div>`:''}${state.dictLang!=='en'&&item.fr?`<div><b>Français :</b> ${escapeHtml(item.fr)}</div>`:''}${state.dictLang!=='fr'&&item.en?`<div><b>English :</b> ${escapeHtml(item.en)}</div>`:''}<small>${escapeHtml(item.category||'Dictionnaire')}</small></div>`).join('')
}
function setDictLang(lang){state.dictLang=lang;document.querySelectorAll('.dictLangButtons button').forEach(btn=>btn.classList.remove('active'));if(lang==='both')document.querySelector('#dictBothBtn').classList.add('active');if(lang==='fr')document.querySelector('#dictFrBtn').classList.add('active');if(lang==='en')document.querySelector('#dictEnBtn').classList.add('active');renderDictionaryResults()}
export function installHebrewWordClick(){document.querySelectorAll('.clickableHe').forEach(el=>{el.addEventListener('dblclick',()=>{const selection=window.getSelection().toString().trim();if(selection)openDictionary(selection)})})}
export function initDictionaryEvents(){document.querySelector('#dictBtn')?.addEventListener('click',()=>openDictionary());document.querySelector('#closeDictBtn')?.addEventListener('click',closeDictionary);document.querySelector('#dictOverlay')?.addEventListener('click',closeDictionary);document.querySelector('#dictSearch')?.addEventListener('input',renderDictionaryResults);document.querySelector('#dictBothBtn')?.addEventListener('click',()=>setDictLang('both'));document.querySelector('#dictFrBtn')?.addEventListener('click',()=>setDictLang('fr'));document.querySelector('#dictEnBtn')?.addEventListener('click',()=>setDictLang('en'))}
