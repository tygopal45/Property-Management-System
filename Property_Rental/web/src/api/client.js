// One place that talks to the API. Every call sends the login cookie and nothing else —
// the token is httpOnly, so this file never sees it and cannot leak it.

async function request(path, { method = 'GET', body } = {}) {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })

  if (response.status === 204) return null

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    // The server explains its own rejections; the UI shows that message rather than
    // inventing one, because the requirement asks for a message that says why.
    const message = payload?.detail ?? `Request failed (${response.status})`
    throw Object.assign(new Error(message), { status: response.status })
  }
  return payload
}

export const api = {
  health: () => request('/health'),
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  units: (includeArchived = false) => request(`/units?include_archived=${includeArchived}`),
  unit: (id) => request(`/units/${id}`),
}
