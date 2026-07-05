// Vercel Serverless Function
// Endpoint: /api/correction-fr
//
// Corrige un champ "fr" dans public/data/merged/<masechet>.json
// Supporte les gros fichiers JSON GitHub via download_url.
//
// Variables Vercel nécessaires :
// ADMIN_PASSWORD
// GITHUB_TOKEN
// GITHUB_OWNER=azernjj
// GITHUB_REPO=talmudai
// GITHUB_BRANCH=main

const MERGED_DIR = 'public/data/merged'

function jsonResponse(res, status, obj) {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(obj, null, 2))
}

function cleanFileName(file) {
  const value = String(file || '').trim()
  if (!/^[a-z0-9\-]+\.json$/i.test(value)) {
    throw new Error('Nom de fichier invalide: ' + value)
  }
  return value
}

function cleanDaf(daf) {
  const value = String(daf || '').trim()
  if (!/^\d+[ab]$/.test(value)) {
    throw new Error('Daf invalide: ' + value)
  }
  return value
}

function cleanType(type) {
  const value = String(type || '').trim()
  if (!['segments', 'rashi', 'tosafot'].includes(value)) {
    throw new Error('Type invalide: ' + value)
  }
  return value
}

async function githubRequest(url, options = {}, debug = {}) {
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

  try {
    data = text ? JSON.parse(text) : {}
  } catch {
    data = { raw: text }
  }

  if (!response.ok) {
    const err = new Error(data.message || `GitHub HTTP ${response.status}`)
    err.githubDebug = {
      ...debug,
      url,
      status: response.status,
      statusText: response.statusText,
      githubMessage: data.message || null,
      githubResponse: data
    }
    throw err
  }

  return data
}

function decodeBase64Utf8(base64) {
  return Buffer.from(base64, 'base64').toString('utf8')
}

function encodeBase64Utf8(text) {
  return Buffer.from(text, 'utf8').toString('base64')
}

async function getGithubFileText(fileInfo) {
  if (fileInfo.content && String(fileInfo.content).trim()) {
    return decodeBase64Utf8(fileInfo.content)
  }

  if (fileInfo.download_url) {
    const rawRes = await fetch(fileInfo.download_url, {
      headers: {
        Authorization: `Bearer ${process.env.GITHUB_TOKEN}`,
        Accept: 'application/vnd.github.raw'
      }
    })

    if (!rawRes.ok) {
      throw new Error(`Impossible de télécharger le JSON brut : ${rawRes.status}`)
    }

    return await rawRes.text()
  }

  throw new Error('GitHub ne renvoie pas le contenu du fichier.')
}

export default async function handler(req, res) {
  const debugInfo = {
    method: req.method,
    env: {
      hasAdminPassword: !!process.env.ADMIN_PASSWORD,
      hasGithubToken: !!process.env.GITHUB_TOKEN,
      githubTokenPrefix: process.env.GITHUB_TOKEN ? process.env.GITHUB_TOKEN.slice(0, 4) + '...' : null,
      githubOwner: process.env.GITHUB_OWNER || null,
      githubRepo: process.env.GITHUB_REPO || null,
      githubBranch: process.env.GITHUB_BRANCH || null
    }
  }

  if (req.method !== 'POST') {
    return jsonResponse(res, 405, {
      error: 'Méthode non autorisée. Cette API attend POST.',
      debug: debugInfo
    })
  }

  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {})

    debugInfo.bodyReceived = {
      file: body.file,
      daf: body.daf,
      type: body.type,
      index: body.index,
      hasPassword: !!body.password,
      hasValue: !!body.value
    }

    const adminPassword = process.env.ADMIN_PASSWORD
    if (!adminPassword) {
      return jsonResponse(res, 500, {
        error: 'ADMIN_PASSWORD manquant dans Vercel.',
        debug: debugInfo
      })
    }

    if (body.password !== adminPassword) {
      return jsonResponse(res, 401, {
        error: 'Code admin incorrect.',
        debug: {
          ...debugInfo,
          passwordLengthReceived: body.password ? String(body.password).length : 0,
          passwordLengthExpected: String(adminPassword).length
        }
      })
    }

    const file = cleanFileName(body.file)
    const daf = cleanDaf(body.daf)
    const type = cleanType(body.type)
    const index = Number(body.index)
    const value = String(body.value || '').trim()

    if (!Number.isInteger(index) || index < 0) {
      return jsonResponse(res, 400, {
        error: 'Index invalide.',
        debug: debugInfo
      })
    }

    if (!value) {
      return jsonResponse(res, 400, {
        error: 'Correction vide.',
        debug: debugInfo
      })
    }

    const owner = process.env.GITHUB_OWNER || 'azernjj'
    const repo = process.env.GITHUB_REPO || 'talmudai'
    const branch = process.env.GITHUB_BRANCH || 'main'
    const jsonPath = `${MERGED_DIR}/${file}`
    const encodedPath = encodeURIComponent(jsonPath).replaceAll('%2F', '/')
    const url = `https://api.github.com/repos/${owner}/${repo}/contents/${encodedPath}?ref=${encodeURIComponent(branch)}`

    debugInfo.githubTarget = { owner, repo, branch, jsonPath, encodedPath, url }

    const fileInfo = await githubRequest(url, {}, debugInfo.githubTarget)

    debugInfo.githubFileFound = {
      sha: fileInfo.sha,
      path: fileInfo.path,
      size: fileInfo.size,
      name: fileInfo.name,
      hasContent: !!fileInfo.content,
      hasDownloadUrl: !!fileInfo.download_url
    }

    const currentJson = await getGithubFileText(fileInfo)

    if (!currentJson || !currentJson.trim()) {
      throw new Error('Le contenu JSON récupéré est vide.')
    }

    const data = JSON.parse(currentJson)

    if (!data.dapim || !data.dapim[daf]) {
      return jsonResponse(res, 404, {
        error: 'Daf introuvable dans le JSON.',
        debug: {
          ...debugInfo,
          availableDapimSample: Object.keys(data.dapim || {}).slice(0, 20)
        }
      })
    }

    const arr = data.dapim[daf][type]
    if (!Array.isArray(arr) || !arr[index]) {
      return jsonResponse(res, 404, {
        error: 'Segment introuvable dans le JSON.',
        debug: {
          ...debugInfo,
          arrayLength: Array.isArray(arr) ? arr.length : null
        }
      })
    }

    const oldValue = arr[index].fr || ''
    arr[index].fr = value

    data.corrections = Array.isArray(data.corrections) ? data.corrections : []
    data.corrections.push({
      date: new Date().toISOString(),
      daf,
      type,
      index,
      oldFr: oldValue,
      newFr: value
    })

    const newContent = JSON.stringify(data, null, 2) + '\n'
    const commitMessage = `Correction FR ${file} ${daf} ${type} ${index + 1}`

    const update = await githubRequest(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: commitMessage,
        content: encodeBase64Utf8(newContent),
        sha: fileInfo.sha,
        branch
      })
    }, debugInfo.githubTarget)

    return jsonResponse(res, 200, {
      ok: true,
      message: 'Correction enregistrée.',
      file,
      daf,
      type,
      index,
      path: jsonPath,
      commit: update.commit?.sha || null,
      debug: debugInfo
    })
  } catch (e) {
    return jsonResponse(res, 500, {
      error: e.message,
      githubDebug: e.githubDebug || null,
      debug: debugInfo
    })
  }
}

