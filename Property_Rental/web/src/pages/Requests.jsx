import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime } from '../format.js'
import { SearchIcon, FilterIcon, ChevronRightIcon, AlertCircleIcon } from '../components/Icons.jsx'

/* Requirement 6: one list, searched, filtered, sorted and paged — on the server.
 *
 * Every control below turns into a query parameter and a round trip. Nothing is filtered in the
 * browser, which the requirement asks for outright: "do not load every request into the browser
 * and filter there." The page shows `total` from the server rather than counting the rows it was
 * given, because counting the rows would only ever report the page size.
 *
 * The filters live in the URL rather than in component state, so a filtered list can be sent to
 * someone, reloaded, and walked back to with the browser's own Back button. */

const PAGE_SIZE = 10
const SORTS = [
  ['created_at', 'Newest first'],
  ['priority', 'Most urgent first'],
  ['status', 'Workflow order'],
]

export default function Requests({ user }) {
  const [params, setParams] = useSearchParams()
  const [page, setPage] = useState({ items: [], total: 0 })
  const [units, setUnits] = useState([])
  const [contractors, setContractors] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  // What the box shows while typing, kept apart from `q` in URL so every keystroke isn't a request
  const [typed, setTyped] = useState(params.get('q') ?? '')

  const current = Number(params.get('page') ?? 1)

  useEffect(() => {
    setLoading(true)
    api
      .requests({
        q: params.get('q'),
        unit_id: params.get('unit_id'),
        status: params.get('status'),
        contractor_id: params.get('contractor_id'),
        priority: params.get('priority'),
        sort: params.get('sort') ?? 'created_at',
        page: current,
        page_size: PAGE_SIZE,
      })
      .then(setPage)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [params, current])

  useEffect(() => {
    api.units().then(setUnits).catch(() => setUnits([]))
    if (user.role === 'manager') api.contractors().then(setContractors).catch(() => setContractors([]))
  }, [user.role])

  function set(key, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('page')
    setParams(next)
  }

  function goTo(nextPage) {
    const next = new URLSearchParams(params)
    next.set('page', String(nextPage))
    setParams(next)
  }

  const lastPage = Math.max(1, Math.ceil(page.total / PAGE_SIZE))

  return (
    <section>
      <div className="page-header">
        <div>
          <h2>Maintenance requests</h2>
          <p className="muted" style={{ margin: 0 }}>
            {user.role === 'manager' ? 'All requests across the entire portfolio' : 'Requests assigned to you'}
          </p>
        </div>
      </div>

      {error && (
        <div className="error">
          <AlertCircleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault()
            set('q', typed.trim())
          }}
          style={{ alignItems: 'flex-end' }}
        >
          <label style={{ flex: '2 1 18rem', marginBottom: 0 }}>
            <span>Search descriptions</span>
            <div style={{ position: 'relative' }}>
              <input
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                placeholder="e.g. boiler, leaking faucet, window latch…"
                style={{ paddingLeft: '2.25rem', maxWidth: '100%' }}
              />
              <div style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)', display: 'flex', pointerEvents: 'none' }}>
                <SearchIcon size={16} />
              </div>
            </div>
          </label>
          <button type="submit" className="primary" style={{ height: '38px' }}>
            Search
          </button>
        </form>

        <div className="row" style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--line)', alignItems: 'flex-end' }}>
          <Filter
            label="Unit"
            value={params.get('unit_id')}
            onChange={(v) => set('unit_id', v)}
            options={units.map((u) => [u.id, `${u.unit_number} — ${u.address}`])}
          />
          <Filter
            label="Status"
            value={params.get('status')}
            onChange={(v) => set('status', v)}
            options={['reported', 'triaged', 'scheduled', 'resolved'].map((s) => [s, s])}
          />
          <Filter
            label="Priority"
            value={params.get('priority')}
            onChange={(v) => set('priority', v)}
            options={['urgent', 'high', 'medium', 'low'].map((p) => [p, p])}
          />
          {user.role === 'manager' && (
            <Filter
              label="Contractor"
              value={params.get('contractor_id')}
              onChange={(v) => set('contractor_id', v)}
              options={contractors.map((c) => [c.id, c.name])}
            />
          )}
          <label style={{ marginBottom: 0 }}>
            <span>Sort</span>
            <select value={params.get('sort') ?? 'created_at'} onChange={(e) => set('sort', e.target.value)} style={{ width: 'auto', minWidth: '10rem' }}>
              {SORTS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '0.85rem 1.25rem', background: '#f8fafc', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Showing {page.items.length} of {page.total} requests
          </span>
          {loading && <span className="muted" style={{ fontSize: '0.8rem' }}>Updating…</span>}
        </div>

        {page.items.length === 0 ? (
          <div style={{ padding: '3rem 1.5rem', textAlign: 'center' }}>
            <p className="muted" style={{ margin: 0, fontSize: '0.95rem' }}>
              {loading ? 'Loading requests…' : 'No requests match your current filters.'}
            </p>
          </div>
        ) : (
          <div className="table-wrap" style={{ margin: 0, border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '70px' }}>ID</th>
                  <th style={{ width: '90px' }}>Unit</th>
                  <th>Description</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Assigned</th>
                  <th>Raised</th>
                  <th style={{ width: '40px' }} />
                </tr>
              </thead>
              <tbody>
                {page.items.map((req) => {
                  const assigned = req.contractors ?? []
                  return (
                    <tr key={req.id}>
                      <td style={{ fontWeight: 600, color: 'var(--muted)' }}>#{req.id}</td>
                      <td>
                        <span style={{ fontWeight: 600, color: 'var(--ink)' }}>{unitNumber(units, req.unit_id)}</span>
                      </td>
                      <td>
                        <Link to={`/requests/${req.id}`} style={{ fontWeight: 600 }}>
                          {req.description}
                        </Link>
                      </td>
                      <td>
                        <span className={`tag ${req.priority}`}>{req.priority}</span>
                      </td>
                      <td>
                        <span className={`tag ${req.status}`}>{req.status}</span>
                      </td>
                      <td>
                        {assigned.length === 0 ? (
                          <span className="muted" style={{ fontSize: '0.8rem' }}>nobody yet</span>
                        ) : (
                          <span style={{ fontSize: '0.85rem', color: 'var(--ink)' }}>
                            {assigned.map((c) => c.name).join(', ')}
                          </span>
                        )}
                      </td>
                      <td className="muted" style={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>
                        {dateTime(req.created_at)}
                      </td>
                      <td>
                        <Link to={`/requests/${req.id}`} style={{ display: 'inline-flex', color: 'var(--muted)' }}>
                          <ChevronRightIcon size={16} />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {lastPage > 1 && (
          <div style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button
              disabled={current <= 1 || loading}
              onClick={() => goTo(current - 1)}
              style={{ padding: '0.4rem 0.8rem', fontSize: '0.825rem' }}
            >
              Previous
            </button>
            <span className="muted" style={{ fontSize: '0.825rem', fontWeight: 500 }}>
              Page {current} of {lastPage}
            </span>
            <button
              disabled={current >= lastPage || loading}
              onClick={() => goTo(current + 1)}
              style={{ padding: '0.4rem 0.8rem', fontSize: '0.825rem' }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </section>
  )
}

function Filter({ label, value, onChange, options }) {
  return (
    <label style={{ marginBottom: 0 }}>
      <span>{label}</span>
      <select value={value ?? ''} onChange={(event) => onChange(event.target.value)} style={{ width: 'auto', minWidth: '8.5rem' }}>
        <option value="">All</option>
        {options.map(([optVal, optLabel]) => (
          <option key={optVal} value={optVal}>{optLabel}</option>
        ))}
      </select>
    </label>
  )
}

function unitNumber(units, unitId) {
  return units?.find((u) => u.id === unitId)?.unit_number ?? `#${unitId}`
}

