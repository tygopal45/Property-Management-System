import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { money, shortDate } from '../format.js'
import {
  RequestIcon,
  AlertCircleIcon,
  CheckCircleIcon,
  RentIcon,
  ClockIcon,
  UserIcon,
} from '../components/Icons.jsx'

/* Requirement 8. One request fills this whole screen — see `routers/dashboard.py` for why. */

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.dashboard().then(setData).catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="error"><AlertCircleIcon size={16} /><span>{error}</span></div>
  if (!data) return <p className="muted">Loading…</p>

  const { headline } = data

  return (
    <section>
      <div className="page-header">
        <div>
          <h2>Dashboard</h2>
          <p className="muted" style={{ margin: 0 }}>Overview of portfolio maintenance and rental operations</p>
        </div>
      </div>

      <div className="grid" style={{ marginBottom: '1.5rem' }}>
        <KpiCard
          value={headline.open_requests}
          label="Open maintenance requests"
          icon={RequestIcon}
          color="var(--accent)"
          bg="var(--accent-light)"
        />
        <KpiCard
          value={headline.units_rent_overdue}
          label="Units with rent overdue this month"
          icon={AlertCircleIcon}
          color="var(--bad)"
          bg="var(--bad-light)"
        />
        <KpiCard
          value={headline.resolved_this_week}
          label="Requests resolved this week"
          icon={CheckCircleIcon}
          color="var(--good)"
          bg="var(--good-light)"
        />
        <KpiCard
          value={money(headline.rent_collected_this_month)}
          label="Rent collected this month"
          icon={RentIcon}
          color="var(--purple)"
          bg="var(--purple-light)"
        />
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>Requests resolved per week</h3>
          <span className="muted" style={{ fontSize: '0.8rem' }}>Last 8 weeks</span>
        </div>
        <Chart weeks={data.resolved_per_week} />
        <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.75rem', marginBottom: 0 }}>
          Counted from the timeline rather than from each request's resolved date, so reopening a
          request cannot change a week that has already been reported.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(20rem, 1fr))', gap: '1.25rem' }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <h3>Requests by status</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Status</th><th className="num">Requests</th><th style={{ width: '40%' }}>Share</th></tr>
              </thead>
              <tbody>
                {(() => {
                  const total = Object.values(data.by_status).reduce((a, b) => a + b, 0) || 1
                  return Object.entries(data.by_status).map(([status, count]) => {
                    const pct = Math.round((count / total) * 100)
                    return (
                      <tr key={status}>
                        <td><span className={`tag ${status}`}>{status}</span></td>
                        <td className="num" style={{ fontWeight: 600 }}>{count}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{ flex: 1, height: '6px', background: 'var(--surface-alt)', borderRadius: '3px', overflow: 'hidden' }}>
                              <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent)', borderRadius: '3px' }} />
                            </div>
                            <span className="muted" style={{ fontSize: '0.75rem', minWidth: '2.2rem' }}>{pct}%</span>
                          </div>
                        </td>
                      </tr>
                    )
                  })
                })()}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 0 }}>
          <h3>Requests by contractor</h3>
          {data.by_contractor.length === 0 ? (
            <p className="muted">No contractors yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Contractor</th><th className="num">Open</th><th className="num">All time</th></tr>
                </thead>
                <tbody>
                  {data.by_contractor.map((load) => {
                    const initial = load.name ? load.name.charAt(0).toUpperCase() : 'C'
                    return (
                      <tr key={load.contractor_id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div className="user-avatar" style={{ width: '24px', height: '24px', fontSize: '0.75rem' }}>{initial}</div>
                            <span style={{ fontWeight: 500 }}>{load.name}</span>
                          </div>
                        </td>
                        <td className="num">
                          <span className={`tag ${load.open_requests > 0 ? 'scheduled' : ''}`} style={{ padding: '0.1rem 0.45rem' }}>
                            {load.open_requests}
                          </span>
                        </td>
                        <td className="num" style={{ color: 'var(--muted)' }}>{load.total_requests}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function KpiCard({ value, label, icon: Icon, color, bg }) {
  return (
    <div className="card" style={{ marginBottom: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: '1.25rem' }}>
      <div className="figure">
        <div className="value">{value}</div>
        <div className="label">{label}</div>
      </div>
      <div
        style={{
          width: '42px',
          height: '42px',
          borderRadius: 'var(--radius-md)',
          background: bg,
          color: color,
          border: '1px solid ' + color,
          boxShadow: '0 0 12px ' + bg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Icon size={22} />
      </div>
    </div>
  )
}

function Chart({ weeks }) {
  // Scale against tallest bar, floor 1 so quiet 8 weeks doesn't divide by 0
  const tallest = Math.max(1, ...weeks.map((week) => week.resolved))

  return (
    <div className="chart">
      {weeks.map((week) => (
        <div className="bar" key={week.week_start}>
          <div className="count">{week.resolved}</div>
          <div
            className={`fill${week.resolved === 0 ? ' empty' : ''}`}
            style={{ height: `${(week.resolved / tallest) * 100}%` }}
            title={`${week.resolved} resolved in week of ${week.week_start}`}
          />
          <div className="week">{shortDate(week.week_start)}</div>
        </div>
      ))}
    </div>
  )
}
