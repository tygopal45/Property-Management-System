import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime, money, monthName, shortDate } from '../format.js'

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

  // One place for every action, so one place clears the last error, reloads, and shows the
  // server's own sentence when it refuses. Same shape as the request screen.
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

  if (error && !unit) return <p className="error">{error}</p>
  if (!unit) return <p className="muted">Loading…</p>

  return (
    <section>
      <p className="muted"><Link to="/units">← All units</Link></p>
      <h2>
        Unit {unit.unit_number}{' '}
        {unit.archived_at && <span className="tag">archived</span>}
      </h2>
      <p className="muted">
        {unit.address} · tenant {unit.tenant_name}
        {isManager && <> · rent now {unit.current_rent ? money(unit.current_rent) : '—'}</>}
      </p>

      {error && <p className="error">{error}</p>}

      {unit.archived_at && (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
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
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <h3 style={{ margin: 0 }}>Details</h3>
                <div className="row">
                  <button onClick={() => setEditing(true)} disabled={busy}>Edit</button>
                  {unit.archived_at ? (
                    <button onClick={() => act(() => api.restoreUnit(id))} disabled={busy}>
                      Restore
                    </button>
                  ) : (
                    <button onClick={() => act(() => api.archiveUnit(id))} disabled={busy}>
                      Archive
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

      <h3>Maintenance requests</h3>
      {requests.length === 0 ? (
        <p className="muted">
          {isManager ? 'No requests against this unit.' : 'None of this unit’s requests are assigned to you.'}
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Description</th>
              <th>Priority</th>
              <th>Status</th>
              <th>Raised</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((request) => (
              <tr key={request.id}>
                <td><Link to={`/requests/${request.id}`}>{request.id}</Link></td>
                <td>{request.description}</td>
                <td><span className={`tag ${request.priority}`}>{request.priority}</span></td>
                <td><span className={`tag ${request.status}`}>{request.status}</span></td>
                <td>{shortDate(request.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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
    <form className="card" onSubmit={save}>
      <h3>Edit unit {unit.unit_number}</h3>
      <label>
        <span>Address</span>
        <input value={address} onChange={(e) => setAddress(e.target.value)} required maxLength={255} />
      </label>
      <label>
        <span>Tenant name</span>
        <input value={tenantName} onChange={(e) => setTenantName(e.target.value)} required maxLength={120} />
      </label>
      <div className="row">
        <button className="primary" disabled={busy}>Save</button>
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
      <h3>Rent history</h3>
      {history.length === 0 ? (
        <p className="muted">No rent set yet, so no rent is owed for any month.</p>
      ) : (
        <table>
          <thead>
            <tr><th>From</th><th className="num">Monthly rent</th></tr>
          </thead>
          <tbody>
            {history.map((row) => (
              <tr key={row.effective_from}>
                <td>{monthName(row.effective_from)}</td>
                <td className="num">{money(row.monthly_rent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form onSubmit={change} style={{ marginTop: '0.75rem' }}>
        <div className="row">
          <label style={{ margin: 0 }}>
            <span>New rent</span>
            <input
              type="number" step="0.01" min="0" value={rent}
              onChange={(e) => setRent(e.target.value)} required style={{ width: '9rem' }}
            />
          </label>
          <label style={{ margin: 0 }}>
            <span>Applies from</span>
            <input type="month" value={from} onChange={(e) => setFrom(e.target.value)} required />
          </label>
          <button disabled={busy || !rent}>Change rent</button>
        </div>
        <p className="muted" style={{ marginBottom: 0 }}>
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
      <h3>Rent payments</h3>
      <form onSubmit={record}>
        <div className="row">
          <label style={{ margin: 0 }}>
            <span>Amount received</span>
            <input
              type="number" step="0.01" min="0.01" value={amount}
              onChange={(e) => setAmount(e.target.value)} required style={{ width: '9rem' }}
            />
          </label>
          <label style={{ margin: 0 }}>
            <span>Covers month</span>
            <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} required />
          </label>
          <button className="primary" disabled={busy || !amount}>Record payment</button>
        </div>
      </form>
      {payments.length === 0 ? (
        <p className="muted" style={{ marginBottom: 0 }}>Nothing recorded against this unit yet.</p>
      ) : (
        <table style={{ marginTop: '0.75rem' }}>
          <thead>
            <tr><th>Covers</th><th className="num">Amount</th><th>Entered</th></tr>
          </thead>
          <tbody>
            {payments.map((payment) => (
              <tr key={payment.id}>
                <td>{monthName(payment.period_month)}</td>
                <td className="num">{money(payment.amount)}</td>
                <td className="muted">{dateTime(payment.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="muted" style={{ marginBottom: 0 }}>
        Payments are a list, never a running total. That is what lets one month hold a part
        payment, a late payment and a correction without any of them overwriting the others.
      </p>
    </div>
  )
}
