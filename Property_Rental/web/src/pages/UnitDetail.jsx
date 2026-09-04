import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime, money, monthName, shortDate } from '../format.js'
import { AlertCircleIcon, UnitIcon, RentIcon, RequestIcon, PlusIcon, ChevronRightIcon } from '../components/Icons.jsx'

/* Requirement 2 on one screen, plus requirement 3's "opening a unit shows its requests".
 *
 * Role-aware, and not by hiding things: the API omits `current_rent`, `rent_history` and every
 * payment route for a contractor, so the money sections below are absent because there is
 * nothing to render rather than because CSS moved them out of the way. A contractor opening this
 * page sees where the flat is and which of its jobs are theirs, which is what they need. */

function thisMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

export default function UnitDetail({ user, onChanged }) {
  const { id } = useParams()
  const isManager = user.role === 'manager'

  const [unit, setUnit] = useState(null)
  const [requests, setRequests] = useState([])
  const [payments, setPayments] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)

  const load = useCallback(() => {
    api.unit(id).then(setUnit).catch((err) => setError(err.message))
    api.unitRequests(id).then(setRequests).catch(() => setRequests([]))
    if (isManager) api.payments(id).then(setPayments).catch(() => setPayments([]))
  }, [id, isManager])

  useEffect(load, [load])

  async function act(fn) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      load()
      onChanged?.()
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setBusy(false)
    }
  }

  if (error && !unit) return <div className="error"><AlertCircleIcon size={16} /><span>{error}</span></div>
  if (!unit) return <p className="muted">Loading…</p>

  return (
    <section>
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/units" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.875rem' }}>
          ← All units
        </Link>
      </div>

      <div className="page-header" style={{ alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <h2>Unit {unit.unit_number}</h2>
            {unit.archived_at ? (
              <span className="tag not_due">archived</span>
            ) : (
              <span className="tag matched">Active</span>
            )}
          </div>
          <p className="muted" style={{ margin: '0.25rem 0 0' }}>
            {unit.address} · Tenant: <strong style={{ color: 'var(--ink)' }}>{unit.tenant_name}</strong>
            {isManager && <> · Current rent: <strong style={{ color: 'var(--ink)' }}>{unit.current_rent ? money(unit.current_rent) : '—'}</strong></>}
          </p>
        </div>
      </div>

      {error && (
        <div className="error">
          <AlertCircleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      {unit.archived_at && (
        <div className="card" style={{ background: 'var(--warn-light)', borderColor: 'var(--warn-border)' }}>
          <p className="muted" style={{ margin: 0, color: 'var(--warn)' }}>
            Archived on {shortDate(unit.archived_at)}. The row is kept rather than deleted, so its
            payments and maintenance requests still point at something real — and no rent is owed
            for the archiving month or any month after it, which is what stops an empty flat
            raising a fresh overdue alert every month for ever.
          </p>
        </div>
      )}

      {isManager && (
        <>
          {editing ? (
            <EditUnit unit={unit} busy={busy} act={act} onDone={() => setEditing(false)} />
          ) : (
            <div className="card">
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: '0 0 0.25rem' }}>Unit Settings & State</h3>
                  <span className="muted" style={{ fontSize: '0.8rem' }}>Update address, tenant, or archive status</span>
                </div>
                <div className="row">
                  <button onClick={() => setEditing(true)} disabled={busy}>Edit details</button>
                  {unit.archived_at ? (
                    <button className="primary" onClick={() => act(() => api.restoreUnit(id))} disabled={busy}>
                      Restore unit
                    </button>
                  ) : (
                    <button className="danger" onClick={() => act(() => api.archiveUnit(id))} disabled={busy}>
                      Archive unit
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}

          <RentHistory unit={unit} busy={busy} act={act} />
          <Payments unitId={id} payments={payments} busy={busy} act={act} />
        </>
      )}

      <div className="card">
        <h3 style={{ margin: '0 0 0.75rem' }}>Maintenance requests</h3>
        {requests.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            {isManager ? 'No requests against this unit.' : 'None of this unit’s requests are assigned to you.'}
          </p>
        ) : (
          <div className="table-wrap" style={{ margin: 0 }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '70px' }}>#</th>
                  <th>Description</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Raised</th>
                  <th style={{ width: '40px' }} />
                </tr>
              </thead>
              <tbody>
                {requests.map((request) => (
                  <tr key={request.id}>
                    <td style={{ fontWeight: 600, color: 'var(--muted)' }}>#{request.id}</td>
                    <td>
                      <Link to={`/requests/${request.id}`} style={{ fontWeight: 600 }}>
                        {request.description}
                      </Link>
                    </td>
                    <td><span className={`tag ${request.priority}`}>{request.priority}</span></td>
                    <td><span className={`tag ${request.status}`}>{request.status}</span></td>
                    <td className="muted">{shortDate(request.created_at)}</td>
                    <td>
                      <Link to={`/requests/${request.id}`} style={{ color: 'var(--muted)', display: 'inline-flex' }}>
                        <ChevronRightIcon size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}

/* Editing a unit changes where it is and who lives there. It deliberately cannot change the
 * rent — a rent change is a new row with a start month, below — and it cannot change the unit
 * number, because that is the identifier the bulk paste matches on. */
function EditUnit({ unit, busy, act, onDone }) {
  const [address, setAddress] = useState(unit.address)
  const [tenantName, setTenantName] = useState(unit.tenant_name)

  async function save(event) {
    event.preventDefault()
    const ok = await act(() => api.updateUnit(unit.id, { address, tenant_name: tenantName }))
    if (ok) onDone()
  }

  return (
    <form className="card" onSubmit={save} style={{ border: '2px solid var(--accent)' }}>
      <h3 style={{ color: 'var(--accent)' }}>Edit unit {unit.unit_number}</h3>
      <div className="grid">
        <label>
          <span>Address</span>
          <input value={address} onChange={(e) => setAddress(e.target.value)} required maxLength={255} />
        </label>
        <label>
          <span>Tenant name</span>
          <input value={tenantName} onChange={(e) => setTenantName(e.target.value)} required maxLength={120} />
        </label>
      </div>
      <div className="row" style={{ marginTop: '0.75rem' }}>
        <button type="submit" className="primary" disabled={busy}>Save</button>
        <button type="button" onClick={onDone} disabled={busy}>Cancel</button>
      </div>
    </form>
  )
}

/* The rent history, newest first, and the form that adds to it.
 *
 * This is the design decision I would most want read on this screen. Rent is not a column on the
 * unit — it is a list of rates with start months — so raising the rent in September cannot
 * re-price July and chase a tenant who paid July in full. `schema.md` §4b. */
function RentHistory({ unit, busy, act }) {
  const [rent, setRent] = useState('')
  const [from, setFrom] = useState(thisMonth)
  const history = [...(unit.rent_history ?? [])].sort((a, b) =>
    a.effective_from < b.effective_from ? 1 : -1,
  )

  async function change(event) {
    event.preventDefault()
    const ok = await act(() =>
      api.changeRent(unit.id, { monthly_rent: rent, effective_from: `${from}-01` }),
    )
    if (ok) setRent('')
  }

  return (
    <div className="card">
      <h3 style={{ margin: '0 0 0.5rem' }}>Rent history</h3>
      {history.length === 0 ? (
        <p className="muted">No rent set yet, so no rent is owed for any month.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Effective From</th><th className="num">Monthly rent</th></tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.effective_from}>
                  <td>{monthName(row.effective_from)}</td>
                  <td className="num" style={{ fontWeight: 600 }}>{money(row.monthly_rent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form onSubmit={change} style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--line)' }}>
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <label style={{ margin: 0 }}>
            <span>New rent</span>
            <input
              type="number" step="0.01" min="0" value={rent}
              onChange={(e) => setRent(e.target.value)} required style={{ width: '9rem' }}
              placeholder="e.g. 1300.00"
            />
          </label>
          <label style={{ margin: 0 }}>
            <span>Applies from</span>
            <input type="month" value={from} onChange={(e) => setFrom(e.target.value)} required style={{ width: 'auto' }} />
          </label>
          <button type="submit" disabled={busy || !rent} className="primary" style={{ height: '38px' }}>
            Change rent
          </button>
        </div>
        <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.5rem', marginBottom: 0 }}>
          Adds a rate rather than overwriting one. Months before this start month keep the rent
          they were actually charged.
        </p>
      </form>
    </div>
  )
}

/* Requirement 2's payments. Two different dates live here and keeping them apart is the point:
 * `period_month` is which month the money pays for, and `created_at` is when it was entered —
 * so July's rent can be recorded in September and still count against July. */
function Payments({ unitId, payments, busy, act }) {
  const [amount, setAmount] = useState('')
  const [month, setMonth] = useState(thisMonth)

  async function record(event) {
    event.preventDefault()
    const ok = await act(() =>
      api.recordPayment(unitId, { amount, period_month: `${month}-01` }),
    )
    if (ok) setAmount('')
  }

  return (
    <div className="card">
      <h3 style={{ margin: '0 0 0.5rem' }}>Rent payments</h3>
      <form onSubmit={record} style={{ marginBottom: '1rem' }}>
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <label style={{ margin: 0 }}>
            <span>Amount received</span>
            <input
              type="number" step="0.01" min="0.01" value={amount}
              onChange={(e) => setAmount(e.target.value)} required style={{ width: '10rem' }}
              placeholder="e.g. 1200.00"
            />
          </label>
          <label style={{ margin: 0 }}>
            <span>Covers month</span>
            <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} required style={{ width: 'auto' }} />
          </label>
          <button className="primary" disabled={busy || !amount} style={{ height: '38px' }}>
            Record payment
          </button>
        </div>
      </form>
      {payments.length === 0 ? (
        <p className="muted" style={{ marginBottom: 0 }}>Nothing recorded against this unit yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Covers</th><th className="num">Amount</th><th>Entered</th></tr>
            </thead>
            <tbody>
              {payments.map((payment) => (
                <tr key={payment.id}>
                  <td style={{ fontWeight: 500 }}>{monthName(payment.period_month)}</td>
                  <td className="num" style={{ fontWeight: 600 }}>{money(payment.amount)}</td>
                  <td className="muted">{dateTime(payment.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.75rem', marginBottom: 0 }}>
        Payments are a list, never a running total. That is what lets one month hold a part
        payment, a late payment and a correction without any of them overwriting the others.
      </p>
    </div>
  )
}
