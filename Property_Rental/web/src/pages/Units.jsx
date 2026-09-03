import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { money } from '../format.js'

/* Requirement 2's portfolio list.
 *
 * Archived units are hidden unless asked for, which is the point of archiving rather than
 * deleting: the row stays, its history stays, and it stops cluttering the list. The rent column
 * is absent for a contractor because the API does not send it — requirement 1. */

function thisMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export default function Units({ user }) {
  const isManager = user.role === 'manager'
  const [units, setUnits] = useState(null)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [error, setError] = useState(null)
  const [adding, setAdding] = useState(false)

  const load = useCallback(() => {
    api.units(includeArchived).then(setUnits).catch((err) => setError(err.message))
  }, [includeArchived])

  useEffect(load, [load])

  return (
    <section>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h2 style={{ margin: 0 }}>Units</h2>
        {isManager && !adding && (
          <button className="primary" onClick={() => setAdding(true)}>Add a unit</button>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {adding && (
        <NewUnit
          onCancel={() => setAdding(false)}
          onCreated={() => { setAdding(false); load() }}
          onError={setError}
        />
      )}

      <label>
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
          style={{ width: 'auto', marginRight: '0.5rem' }}
        />
        Show archived
      </label>

      {!units ? (
        <p className="muted">Loading…</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Unit</th>
              <th>Address</th>
              <th>Tenant</th>
              {isManager && <th className="num">Rent now</th>}
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {units.map((unit) => (
              <tr key={unit.id}>
                <td><Link to={`/units/${unit.id}`}>{unit.unit_number}</Link></td>
                <td>{unit.address}</td>
                <td>{unit.tenant_name}</td>
                {/* The rent in force today, worked out from the rent history by the API. */}
                {isManager && (
                  <td className="num">{unit.current_rent ? money(unit.current_rent) : '—'}</td>
                )}
                <td>
                  {unit.archived_at ? <span className="tag">archived</span> : 'Active'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {units?.length === 0 && <p className="muted">No units to show.</p>}
    </section>
  )
}

/* Creating a unit sets its first rent and the month that rent starts from — not a rent column,
 * the first row of its history. Everything after it is a further row (see the unit page). */
function NewUnit({ onCancel, onCreated, onError }) {
  const [form, setForm] = useState({
    unit_number: '', address: '', tenant_name: '', monthly_rent: '', rent_effective_from: thisMonth(),
  })
  const [busy, setBusy] = useState(false)

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  async function create(event) {
    event.preventDefault()
    setBusy(true)
    onError(null)
    try {
      await api.createUnit({ ...form, rent_effective_from: `${form.rent_effective_from}-01` })
      onCreated()
    } catch (err) {
      onError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={create}>
      <h3>Add a unit</h3>
      <div className="grid">
        <label>
          <span>Unit number</span>
          <input value={form.unit_number} onChange={set('unit_number')} required maxLength={32} />
        </label>
        <label>
          <span>Address</span>
          <input value={form.address} onChange={set('address')} required maxLength={255} />
        </label>
        <label>
          <span>Tenant name</span>
          <input value={form.tenant_name} onChange={set('tenant_name')} required maxLength={120} />
        </label>
        <label>
          <span>Monthly rent</span>
          <input
            type="number" step="0.01" min="0"
            value={form.monthly_rent} onChange={set('monthly_rent')} required
          />
        </label>
        <label>
          <span>Rent applies from</span>
          <input
            type="month" value={form.rent_effective_from}
            onChange={set('rent_effective_from')} required
          />
        </label>
      </div>
      <p className="muted">
        No rent is owed for months before that start month, so adding a unit today does not raise
        a year of overdue alerts behind it.
      </p>
      <div className="row">
        <button className="primary" disabled={busy}>{busy ? 'Adding…' : 'Add unit'}</button>
        <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
      </div>
    </form>
  )
}
