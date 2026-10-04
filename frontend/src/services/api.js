const API_ROOT = '/api/v1'
let csrfToken = null

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function errorMessage(payload, status) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(', ')
  return payload?.message || `Request failed (${status})`
}

async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = new Headers(options.headers)

  if (csrfToken && !['GET', 'HEAD', 'OPTIONS'].includes(method) && path !== '/auth/login') {
    headers.set('X-CSRF-Token', csrfToken)
  }

  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  if (response.status === 204) return null

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json() : null
  if (!response.ok) throw new ApiError(errorMessage(payload, response.status), response.status)
  return payload
}

function jsonRequest(path, method, value) {
  return request(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  })
}

export function setCsrfToken(token) {
  csrfToken = token || null
}

export async function refreshCsrfToken() {
  const result = await request('/auth/refresh-csrf', { method: 'POST' })
  setCsrfToken(result.csrf_token)
  return result.csrf_token
}

export async function checkBackendHealth() {
  const startTime = performance.now()
  try {
    const response = await fetch('/health', { headers: { Accept: 'application/json' } })
    const latency = Math.round(performance.now() - startTime)
    if (!response.ok) throw new ApiError(`Backend returned HTTP ${response.status}`, response.status)
    return { connected: true, latency, data: await response.json() }
  } catch (error) {
    return {
      connected: false,
      latency: Math.round(performance.now() - startTime),
      error: error.message,
      data: { status: 'offline' },
    }
  }
}

export async function getCurrentUser() {
  const auth = await request('/auth/check-auth')
  if (!auth.authenticated) {
    setCsrfToken(null)
    return null
  }
  const user = await request('/users/me')
  await refreshCsrfToken()
  return user
}

export async function loginWithPassword(identifier, password) {
  const form = new URLSearchParams({ username: identifier, password })
  const result = await request('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  })
  setCsrfToken(result.csrf_token)
  return request('/users/me')
}

export async function registerAndLogin({ name, username, email, password }) {
  await jsonRequest('/users/', 'POST', { name, username, email, password })
  return loginWithPassword(username, password)
}

export async function logout() {
  await request('/auth/logout', { method: 'POST' })
  setCsrfToken(null)
}

export function beginGoogleLogin() {
  const query = new URLSearchParams({ redirect_to: '/' })
  window.location.assign(`${API_ROOT}/auth/oauth/google?${query}`)
}

export function listGrievances() {
  return request('/grievances/')
}

export function createGrievance(snapshot) {
  return jsonRequest('/grievances/', 'POST', snapshot)
}

export function startAiGrievance(initialMessage, language = 'en') {
  return jsonRequest('/grievances/start', 'POST', {
    initial_message: initialMessage,
    language,
  })
}

export function submitAiTurn(grievanceId, message, language = 'en') {
  return jsonRequest(`/grievances/${grievanceId}/turns`, 'POST', {
    message,
    language,
  })
}

export function updateGrievance(id, snapshot) {
  return jsonRequest(`/grievances/${id}`, 'PUT', snapshot)
}

export function deleteGrievance(id) {
  return request(`/grievances/${id}`, { method: 'DELETE' })
}
