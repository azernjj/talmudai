import './style.css'
import './design.css'
import { state } from './state.js'
import { renderLayout } from './modules/layout.js'
import { injectMobileStyles, initMobileMenu } from './modules/mobile.js'
import { renderLibrary, loadMasechet, initTalmudEvents } from './modules/talmud.js'
import { initDictionaryEvents } from './modules/dictionary.js'
import { initParashiotEvents } from './modules/parashiot.js'
import { initSearchEvents } from './modules/search.js'
import { initShulchanArukhEvents } from './modules/shulchan-arukh.js'
import { initCorrectionAdminEvents } from './modules/correction-admin.js'
import { initMishnaEvents } from './modules/mishna.js'

const app = document.querySelector('#app')

renderLayout(app)
injectMobileStyles()
initMobileMenu()
initTalmudEvents()
initDictionaryEvents()
initCorrectionAdminEvents()
initParashiotEvents()
initSearchEvents()
initShulchanArukhEvents()
initMishnaEvents()

renderLibrary()
loadMasechet(localStorage.getItem('currentFile') || 'berakhot.json')

window.TALMUD_AI_STATE = state
