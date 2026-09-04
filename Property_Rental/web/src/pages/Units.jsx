import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { money } from '../format.js'
import { PlusIcon, UnitIcon, AlertCircleIcon, ChevronRightIcon } from '../components/Icons.jsx'

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
      <div className="page-header">
        <div>
          <h2>Units</h2>
          <p className="muted" style={{ margin: 0 }}>
            {isManager ? 'Manage rental units, rent history and tenants' : 'Rental units portfolio'}
          </p>
        </div>
        {isManager && !adding && (
          <button className="primary" onClick={() => setAdding(true)}>
            <PlusIcon size={16} />
            <span>Add a unit</span>
          </button>
        )}
      </div>

      {error && (
        <div className="error">
          <AlertCircleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      {adding && (
        <NewUnit
          onCancel={() => setAdding(false)}
          onCreated={() => { setAdding(false); load() }}
          onError={setError}
        />
      )}

      <div className="card" style={{ padding: '0.85rem 1.25rem', marginBottom: '1.25rem' }}>
        <label style={{ margin: 0, display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)}
            style={{ width: 'auto', marginRight: '0.65rem' }}
          />
          <span style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
            Show archived
          </span>
        </label>
      </div>

      {!units ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="table-wrap" style={{ margin: 0, border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '100px' }}>Unit</th>
                  <th>Address</th>
                  <th>Tenant</th>
                  {isManager && <th className="num">Rent now</th>}
                  <th style={{ width: '110px' }}>State</th>
                  <th style={{ width: '40px' }} />
                </tr>
              </thead>
              <tbody>
                {units.map((unit) => {
                  const initial = unit.tenant_name ? unit.tenant_name.charAt(0).toUpperCase() : 'T'
                  return (
                    <tr key={unit.id}>
                      <td>
                        <Link to={`/units/${unit.id}`} style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                          {unit.unit_number}
                        </Link>
                      </td>
                      <td style={{ color: 'var(--text-secondary)' }}>{unit.address}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <div className="user-avatar" style={{ width: '24px', height: '24px', fontSize: '0.75rem' }}>
                            {initial}
                          </div>
                          <span style={{ fontWeight: 500 }}>{unit.tenant_name}</span>
                        </div>
                      </td>
                      {/* The rent in force today, worked out from the rent history by the API. */}
                      {isManager && (
                        <td className="num" style={{ fontWeight: 600 }}>
                          {unit.current_rent ? money(unit.current_rent) : '—'}
                        </td>
                      )}
                      <td>
                        {unit.archived_at ? (
                          <span className="tag not_due">archived</span>
                        ) : (
                          <span className="tag matched">Active</span>
                        )}
                      </td>
                      <td>
                        <Link to={`/units/${unit.id}`} style={{ display: 'inline-flex', color: 'var(--muted)' }}>
                          <ChevronRightIcon size={16} />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {units.length === 0 && (
            <div style={{ padding: '3rem 1.5rem', textAlign: 'center' }}>
              <p className="muted" style={{ margin: 0 }}>No units to show.</p>
            </div>
          )}
        </div>
      )}
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
    <form className="card" onSubmit={create} style={{ border: '2px solid var(--accent)', marginBottom: '1.5rem' }}>
      <h3 style={{ marginBottom: '1rem', color: 'var(--accent)' }}>Add a unit</h3>
      <div className="grid">
        <label>
          <span>Unit number</span>
          <input value={form.unit_number} onChange={set('unit_number')} required maxLength={32} placeholder="e.g. 4B" />
        </label>
        <label>
          <span>Address</span>
          <input value={form.address} onChange={set('address')} required maxLength={255} placeholder="e.g. 12 High Street" />
        </label>
        <label>
          <span>Tenant name</span>
          <input value={form.tenant_name} onChange={set('tenant_name')} required maxLength={120} placeholder="e.g. Maya Lin" />
        </label>
        <label>
          <span>Monthly rent</span>
          <input
            type="number" step="0.01" min="0"
            value={form.monthly_rent} onChange={set('monthly_rent')} required
            placeholder="e.g. 1200.00"
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
      <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.5rem' }}>
        No rent is owed for months before that start month, so adding a unit today does not raise
        a year of overdue alerts behind it.
      </p>
      <div className="row" style={{ marginTop: '1rem' }}>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Adding…' : 'Add unit'}
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </form>
  )
}
