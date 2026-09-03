import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { money, shortDate } from '../format.js'

/* Requirement 8. One request fills this whole screen — see `routers/dashboard.py` for why. */

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.dashboard().then(setData).catch((err) => setError(err.message))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!data) return <p className="muted">Loading…</p>

  const { headline } = data

  return (
    <section>
      <h2>Dashboard</h2>

      <div className="card grid">
        <Figure value={headline.open_requests} label="Open maintenance requests" />
        <Figure value={headline.units_rent_overdue} label="Units with rent overdue this month" />
        <Figure value={headline.resolved_this_week} label="Requests resolved this week" />
        <Figure value={money(headline.rent_collected_this_month)} label="Rent collected this month" />
      </div>

      <div className="card">
        <h3>Requests resolved per week</h3>
        <Chart weeks={data.resolved_per_week} />
        <p className="muted">
          Counted from the timeline rather than from each request's resolved date, so reopening a
          request cannot change a week that has already been reported.
        </p>
      </div>

      <div className="card">
        <h3>Requests by status</h3>
        <table>
          <thead>
            <tr><th>Status</th><th className="num">Requests</th></tr>
          </thead>
          <tbody>
            {Object.entries(data.by_status).map(([status, count]) => (
              <tr key={status}>
                <td><span className={`tag ${status}`}>{status}</span></td>
                <td className="num">{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Requests by contractor</h3>
        <table>
          <thead>
            <tr><th>Contractor</th><th className="num">Open</th><th className="num">All time</th></tr>
          </thead>
          <tbody>
            {data.by_contractor.map((load) => (
              <tr key={load.contractor_id}>
                <td>{load.name}</td>
                <td className="num">{load.open_requests}</td>
                <td className="num">{load.total_requests}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.by_contractor.length === 0 && <p className="muted">No contractors yet.</p>}
      </div>
    </section>
  )
}

function Figure({ value, label }) {
  return (
    <div className="figure">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  )
}

function Chart({ weeks }) {
  // Scale against the tallest bar, with a floor of 1 so a quiet eight weeks does not divide by
  // zero and does not draw eight full-height bars of nothing.
  const tallest = Math.max(1, ...weeks.map((week) => week.resolved))

  return (
    <div className="chart">
      {weeks.map((week) => (
        <div className="bar" key={week.week_start}>
          <div className="count">{week.resolved}</div>
          <div
            className={`fill${week.resolved === 0 ? ' empty' : ''}`}
            style={{ height: `${(week.resolved / tallest) * 100}%` }}
            title={`${week.resolved} resolved in the week of ${week.week_start}`}
          />
          <div className="week">{shortDate(week.week_start)}</div>
        </div>
      ))}
    </div>
  )
}
