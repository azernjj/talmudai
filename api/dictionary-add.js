// Vercel Serverless Function: /api/dictionary-add
// Variables Vercel requises :
// ADMIN_PASSWORD
// GITHUB_TOKEN
// GITHUB_OWNER=azernjj
// GITHUB_REPO=talmudai
// GITHUB_BRANCH=main
// DICTIONARY_PATH=public/data/dictionary/dictionary.json

const DEFAULT_PATH = 'public/data/dictionary/dictionary.json'

function jsonResponse(res, status, obj) {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(obj))
}

function cleanText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function sortObjectKeys(obj) {
  return Object.fromEntries(Object.entries(obj || {}).sort(([a], [b]) => a.localeCompare(b, 'he')))
}

async function githubRequest(url, options = {}) {
  const token = process.env.GITHUB_TOKEN
  if (!token) throw new Error('GITHUB_TOKEN manquant dans Vercel.')

  const response = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(options.headers || {})
    }
  })

  const text = await response.text()
  let data = {}
  try { data = text ? JSON.parse(text) : {} } catch { data = { raw: text } }

  if (!response.ok) throw new Error(data.message || `GitHub HTTP ${response.status}`)
  return data
}

function decodeBase64Utf8(base64) {
  return Buffer.from(base64, 'base64').toString('utf8')
}

function encodeBase64Utf8(text) {
  return Buffer.from(text, 'utf8').toString('base64')
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return jsonResponse(res, 405, { error: 'Méthode non autorisée.' })

  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {})

    const adminPassword = process.env.ADMIN_PASSWORD
    if (!adminPassword) return jsonResponse(res, 500, { error: 'ADMIN_PASSWORD manquant dans Vercel.' })
    if (body.password !== adminPassword) return jsonResponse(res, 401, { error: 'Mot de passe admin incorrect.' })

    const term = cleanText(body.term)
    const fr = cleanText(body.fr)
    const en = cleanText(body.en)
    const note = cleanText(body.note)
    const category = cleanText(body.category || 'aramic') || 'aramic'

    if (!term) return jsonResponse(res, 400, { error: 'Mot / entrée manquant.' })
    if (!fr && !en) return jsonResponse(res, 400, { error: 'Traduction française ou anglaise obligatoire.' })

    const owner = process.env.GITHUB_OWNER || 'azernjj'
    const repo = process.env.GITHUB_REPO || 'talmudai'
    const branch = process.env.GITHUB_BRANCH || 'main'
    const dictionaryPath = process.env.DICTIONARY_PATH || DEFAULT_PATH
    const encodedPath = encodeURIComponent(dictionaryPath).replaceAll('%2F', '/')
    const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodedPath}?ref=${encodeURIComponent(branch)}`

    const file = await githubRequest(url)
    const sha = file.sha
    const currentJson = decodeBase64Utf8(file.content || '')
    const dictionary = JSON.parse(currentJson || '{}')

    if (!dictionary[category] || typeof dictionary[category] !== 'object' || Array.isArray(dictionary[category])) {
      dictionary[category] = {}
    }

    const oldValue = dictionary[category][term]
    let nextValue

    if (en || note) {
      nextValue = { aramic: term, fr, en }
      if (note) nextValue.note = note
    } else {
      nextValue = fr
    }

    dictionary[category][term] = nextValue
    dictionary[category] = sortObjectKeys(dictionary[category])

    const newContent = JSON.stringify(dictionary, null, 2) + '\n'
    const commitMessage = oldValue ? `Update dictionary entry: ${term}` : `Add dictionary entry: ${term}`

    const update = await githubRequest(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: commitMessage,
        content: encodeBase64Utf8(newContent),
        sha,
        branch
      })
    })

    return jsonResponse(res, 200, {
      ok: true,
      path: dictionaryPath,
      term,
      category,
      categoryCount: Object.keys(dictionary[category]).length,
      commit: update.commit?.sha || null
    })
  } catch (e) {
    return jsonResponse(res, 500, { error: e.message })
  }
}
