import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { money, monthName, shortDate } from '../format.js'
import { AlertIcon, AlertCircleIcon, CheckCircleIcon } from '../components/Icons.jsx'

/* Requirement 10: the alerts area, and the dismissal that comes back.
 *
 * Every row here is a **(unit, month) pair**, not a unit, and that is the requirement rather than
 * a display choice. A flat three months behind raises three rows and the badge counts three, so
 * dismissing one leaves the other two — which is the only way "the alert returns in a later
 * month" can be true without a scheduled job anywhere. `schema.md` §5.2 has the argument.
 *
 * The count is not fetched separately. It arrives with the list from the same query, so the badge
 * in the navigation and the rows on this page cannot disagree about how many there are. */

export default function Alerts({ onChanged }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)

  const load = useCallback(() => {
    api.alerts().then(setData).catch((err) => setError(err.message))
  }, [])

  useEffect(load, [load])

  async function dismiss(alert) {
    // Keyed per row rather than one page-wide flag, so dismissing 4B does not grey out 5A.
    setBusy(`${alert.unit_id}:${alert.period_month}`)
    setError(null)
    try {
      await api.dismissAlert(alert.unit_id, alert.period_month)
      load()
      onChanged?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(null)
    }
  }

  if (error && !data) return <div className="error"><AlertCircleIcon size={16} /><span>{error}</span></div>
  if (!data) return <p className="muted">Loading…</p>

  return (
    <section>
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <h2>Rent alerts</h2>
            {data.count > 0 && <span className="badge">{data.count}</span>}
          </div>
          <p className="muted" style={{ margin: 0 }}>
            Units with unpaid or partial rent past the 5-day grace period
          </p>
        </div>
      </div>

      {error && (
        <div className="error">
          <AlertCircleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      {data.count === 0 ? (
        <div className="card" style={{ padding: '3rem 2rem', textAlign: 'center', background: 'var(--good-light)', borderColor: 'var(--good-border)', boxShadow: '0 0 20px rgba(0, 245, 160, 0.15)' }}>
          <div
            style={{
              width: '52px',
              height: '52px',
              borderRadius: '50%',
              background: 'var(--good-light)',
              border: '1px solid var(--good-border)',
              color: 'var(--good)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1rem',
              boxShadow: '0 0 16px rgba(0, 245, 160, 0.35)',
            }}
          >
            <CheckCircleIcon size={30} />
          </div>
          <h3 style={{ margin: '0 0 0.5rem', color: 'var(--good)', fontSize: '1.2rem', textShadow: '0 0 10px rgba(0, 245, 160, 0.3)' }}>
            All clear! No overdue rent
          </h3>
          <p className="muted" style={{ margin: 0, maxWidth: '32rem', marginLeft: 'auto', marginRight: 'auto', color: 'var(--text-secondary)' }}>
            Nothing is outstanding past its grace period. A unit month appears here once it is unpaid or
            part-paid and the grace period for that month has passed.
          </p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '0.85rem 1.25rem', background: 'var(--surface-alt)', borderBottom: '1px solid var(--line)' }}>
            <p className="muted" style={{ margin: 0, fontSize: '0.825rem' }}>
              One row per unit and month. Dismissing a row hides that month only — if rent is short next month, a new alert appears automatically.
            </p>
          </div>
          <div className="table-wrap" style={{ margin: 0, border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '110px' }}>Unit</th>
                  <th>Tenant</th>
                  <th>Month</th>
                  <th className="num">Rent</th>
                  <th className="num">Paid</th>
                  <th className="num">Outstanding</th>
                  <th>Status</th>
                  <th>Overdue since</th>
                  <th style={{ width: '100px' }} />
                </tr>
              </thead>
              <tbody>
                {data.alerts.map((alert) => {
                  const key = `${alert.unit_id}:${alert.period_month}`
                  return (
                    <tr key={key}>
                      <td>
                        <Link to={`/units/${alert.unit_id}`} style={{ fontWeight: 700 }}>
                          {alert.unit_number}
                        </Link>
                        <div className="muted" style={{ fontSize: '0.75rem' }}>{alert.address}</div>
                      </td>
                      <td style={{ fontWeight: 500 }}>{alert.tenant_name}</td>
                      <td style={{ fontWeight: 500 }}>{monthName(alert.period_month)}</td>
                      <td className="num">{money(alert.monthly_rent)}</td>
                      <td className="num" style={{ color: Number(alert.amount_paid) > 0 ? 'var(--good)' : 'var(--muted)' }}>
                        {money(alert.amount_paid)}
                      </td>
                      <td className="num" style={{ fontWeight: 700, color: 'var(--bad)' }}>
                        {money(alert.outstanding)}
                      </td>
                      <td><span className={`tag ${alert.status}`}>{alert.status}</span></td>
                      <td className="muted" style={{ fontSize: '0.825rem' }}>{shortDate(alert.overdue_since)}</td>
                      <td>
                        <button
                          onClick={() => dismiss(alert)}
                          disabled={busy === key}
                          style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem' }}
                        >
                          {busy === key ? 'Dismissing…' : 'Dismiss'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
