import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime } from '../format.js'

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

  // What the box shows while you type, kept apart from `q` in the URL so that every keystroke is
  // not a request. The URL only changes when the search is submitted.
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

  // Changing any filter returns to page 1. Staying on page 4 of a narrower list is how a screen
  // ends up showing "no results" for a search that has plenty.
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
      <h2>Maintenance requests</h2>

      <div className="card">
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault()
            set('q', typed.trim())
          }}
        >
          <label style={{ flex: '2 1 16rem', marginBottom: 0 }}>
            <span>Search descriptions</span>
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              placeholder="boiler, window, damp…"
            />
          </label>
          <button type="submit">Search</button>
        </form>

        <div className="row" style={{ marginTop: '1rem' }}>
          <Filter label="Unit" value={params.get('unit_id')} onChange={(v) => set('unit_id', v)}
            options={units.map((u) => [u.id, `${u.unit_number} — ${u.address}`])} />
          <Filter label="Status" value={params.get('status')} onChange={(v) => set('status', v)}
            options={['reported', 'triaged', 'scheduled', 'resolved'].map((s) => [s, s])} />
          <Filter label="Priority" value={params.get('priority')} onChange={(v) => set('priority', v)}
            options={['urgent', 'high', 'medium', 'low'].map((p) => [p, p])} />
          {user.role === 'manager' && (
            <Filter label="Contractor" value={params.get('contractor_id')}
              onChange={(v) => set('contractor_id', v)}
              options={contractors.map((c) => [c.id, c.name])} />
          )}
          <label style={{ marginBottom: 0 }}>
            <span>Sort</span>
            <select value={params.get('sort') ?? 'created_at'} onChange={(e) => set('sort', e.target.value)}>
              {SORTS.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          {[...params.keys()].length > 0 && (
            <button onClick={() => { setParams(new URLSearchParams()); setTyped('') }}>
              Clear
            </button>
          )}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <p className="muted">
        {loading ? 'Loading…' : `${page.total} matching request${page.total === 1 ? '' : 's'}`}
      </p>

      <table>
        <thead>
          <tr>
            <th>Unit</th>
            <th>Description</th>
            <th>Priority</th>
            <th>Status</th>
            <th>Contractors</th>
            <th>Raised</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((request) => (
            <tr key={request.id}>
              <td>{unitNumber(units, request.unit_id)}</td>
              <td><Link to={`/requests/${request.id}`}>{request.description}</Link></td>
              <td><span className={`tag ${request.priority}`}>{request.priority}</span></td>
              <td><span className={`tag ${request.status}`}>{request.status}</span></td>
              <td>
                {request.contractors.length
                  ? request.contractors.map((c) => c.name).join(', ')
                  : <span className="muted">nobody yet</span>}
              </td>
              <td className="muted">{dateTime(request.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {!loading && page.items.length === 0 && (
        <p className="muted">Nothing matches those filters.</p>
      )}

      {page.total > PAGE_SIZE && (
        <div className="row" style={{ marginTop: '1rem', alignItems: 'center' }}>
          <button disabled={current <= 1} onClick={() => goTo(current - 1)}>Previous</button>
          <span className="muted">Page {current} of {lastPage}</span>
          <button disabled={current >= lastPage} onClick={() => goTo(current + 1)}>Next</button>
        </div>
      )}
    </section>
  )
}

function Filter({ label, value, onChange, options }) {
  return (
    <label style={{ marginBottom: 0 }}>
      <span>{label}</span>
      <select value={value ?? ''} onChange={(event) => onChange(event.target.value)}>
        <option value="">Any</option>
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>{optionLabel}</option>
        ))}
      </select>
    </label>
  )
}

function unitNumber(units, unitId) {
  // A contractor sees only the units they have work on, so a request can arrive for a unit that
  // is not in their list. The id is a worse label than the number but better than a blank cell.
  return units.find((unit) => unit.id === unitId)?.unit_number ?? `#${unitId}`
}
