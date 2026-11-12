const KEY = 'atf_token'
export const getToken = () => localStorage.getItem(KEY) || sessionStorage.getItem(KEY)
export const setToken = (t, remember = true) => { clearToken(); (remember ? localStorage : sessionStorage).setItem(KEY, t) }
export const clearToken = () => { localStorage.removeItem(KEY); sessionStorage.removeItem(KEY) }

async function raw(path, { method = 'GET', body, form } = {}) {
  const h = {}; const t = getToken()
  if (t) h.Authorization = 'Bearer ' + t
  let b
  if (form) b = form
  else if (body) { h['Content-Type'] = 'application/json'; b = JSON.stringify(body) }
  return fetch('/api' + path, { method, headers: h, body: b })
}
export async function api(path, opts) {
  const r = await raw(path, opts)
  if (r.status === 401 && getToken() && !path.startsWith('/auth')) { clearToken(); location.href = '/auth' }
  const j = await r.json().catch(() => ({}))
  if (!r.ok) { const e = new Error(typeof j.detail === 'string' ? j.detail : 'Request failed'); e.status = r.status; e.notConfigured = j.not_configured; throw e }
  return j
}
export async function blobUrl(path) {
  const r = await raw(path); if (!r.ok) throw new Error('Could not load file')
  return URL.createObjectURL(await r.blob())
}
export async function download(path, name) {
  const u = await blobUrl(path); const a = document.createElement('a'); a.href = u; a.download = name; a.click()
}
