export function cleanText(str) {
  return String(str || '').replace(/["“”]/g, '').replace(/\s+/g, ' ').trim()
}
export function escapeHtml(str) {
  return String(str || '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')
}
export function parseDaf(daf) {
  const match = String(daf).match(/^(\d+)([ab])$/)
  return { num: match ? Number(match[1]) : 0, side: match ? match[2] : '' }
}
export function sortDaf(a,b) {
  const pa=parseDaf(a), pb=parseDaf(b)
  if (pa.num !== pb.num) return pa.num-pb.num
  return pa.side.localeCompare(pb.side)
}
export function highlightText(text, q) {
  const safe = escapeHtml(text)
  if (!q) return safe
  const escapedQ = String(q).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return safe.replace(new RegExp(escapedQ, 'gi'), m => `<mark>${m}</mark>`)
}
