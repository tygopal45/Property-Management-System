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
    const message = describe(payload) ?? `Request failed (${response.status})`
    throw Object.assign(new Error(message), { status: response.status })
  }
  return payload
}

function describe(payload) {
  const detail = payload?.detail
  if (!detail) return null
  if (typeof detail === 'string') return detail
  // A 422 from FastAPI is a list of field errors. The first one is the useful one.
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null
    return field ? `${field}: ${first.msg}` : first.msg
  }
  return null
}

// Query strings, skipping anything the caller left empty. Written out rather than pulled in,
// because "" and null must not become filters that match nothing.
function query(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, value)
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  health: () => request('/health'),

  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),

  units: (includeArchived = false) => request(`/units${query({ include_archived: includeArchived })}`),
  unit: (id) => request(`/units/${id}`),
  createUnit: (body) => request('/units', { method: 'POST', body }),
  updateUnit: (id, body) => request(`/units/${id}`, { method: 'PATCH', body }),
  changeRent: (id, body) => request(`/units/${id}/rent`, { method: 'POST', body }),
  archiveUnit: (id) => request(`/units/${id}/archive`, { method: 'POST' }),
  restoreUnit: (id) => request(`/units/${id}/restore`, { method: 'POST' }),
  unitRequests: (id) => request(`/units/${id}/requests`),
  payments: (id, month) => request(`/units/${id}/payments${query({ month })}`),
  recordPayment: (id, body) => request(`/units/${id}/payments`, { method: 'POST', body }),

  requests: (params) => request(`/requests${query(params)}`),
  myRequests: () => request('/requests/mine'),
  requestDetail: (id) => request(`/requests/${id}`),
  createRequest: (body) => request('/requests', { method: 'POST', body }),
  updateRequest: (id, body) => request(`/requests/${id}`, { method: 'PATCH', body }),
  changeStatus: (id, status) => request(`/requests/${id}/status`, { method: 'PATCH', body: { status } }),
  addNote: (id, body) => request(`/requests/${id}/notes`, { method: 'POST', body: { body } }),
  assign: (id, contractorId) =>
    request(`/requests/${id}/assignments`, { method: 'POST', body: { contractor_id: contractorId } }),
  unassign: (id, contractorId) =>
    request(`/requests/${id}/assignments/${contractorId}`, { method: 'DELETE' }),

  dashboard: () => request('/dashboard'),
  alerts: () => request('/alerts'),
  dismissAlert: (unitId, periodMonth) =>
    request('/alerts/dismiss', { method: 'POST', body: { unit_id: unitId, period_month: periodMonth } }),
  rentRoll: (params) => request(`/rent/roll${query(params)}`),
  bulkRent: (body) => request('/rent/bulk', { method: 'POST', body }),
  // Not fetched — the browser downloads it, so this is a URL rather than a call.
  rentRollCsvUrl: (params) => `/api/rent/roll.csv${query(params)}`,
}
