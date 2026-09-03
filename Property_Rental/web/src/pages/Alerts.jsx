import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { money, monthName, shortDate } from '../format.js'

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

  if (error && !data) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Loading…</p>

  return (
    <section>
      <h2>
        Rent alerts{' '}
        {data.count > 0 && <span className="badge">{data.count}</span>}
      </h2>

      {error && <p className="error">{error}</p>}

      {data.count === 0 ? (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            Nothing outstanding past its grace period. A month appears here once it is unpaid or
            part-paid and the grace period for <em>that month</em> has passed.
          </p>
        </div>
      ) : (
        <>
          <p className="muted">
            One row per unit and month. Dismissing a row hides that month only — if the rent is
            still short next month, a new alert appears on its own.
          </p>
          <table>
            <thead>
              <tr>
                <th>Unit</th>
                <th>Tenant</th>
                <th>Month</th>
                <th className="num">Rent</th>
                <th className="num">Paid</th>
                <th className="num">Outstanding</th>
                <th>Status</th>
                <th>Overdue since</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.alerts.map((alert) => {
                const key = `${alert.unit_id}:${alert.period_month}`
                return (
                  <tr key={key}>
                    <td>
                      <Link to={`/units/${alert.unit_id}`}>{alert.unit_number}</Link>
                      <div className="muted">{alert.address}</div>
                    </td>
                    <td>{alert.tenant_name}</td>
                    <td>{monthName(alert.period_month)}</td>
                    <td className="num">{money(alert.monthly_rent)}</td>
                    <td className="num">{money(alert.amount_paid)}</td>
                    <td className="num">{money(alert.outstanding)}</td>
                    <td><span className={`tag ${alert.status}`}>{alert.status}</span></td>
                    <td>{shortDate(alert.overdue_since)}</td>
                    <td>
                      <button onClick={() => dismiss(alert)} disabled={busy === key}>
                        {busy === key ? 'Dismissing…' : 'Dismiss'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}
