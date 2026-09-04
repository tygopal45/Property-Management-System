import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime } from '../format.js'
import { AlertCircleIcon, RequestIcon, CheckCircleIcon, UnitIcon, ChevronRightIcon } from '../components/Icons.jsx'

/* Requirement 5: "every contractor can see one list of every request assigned to them, across
 * every unit." One call, no filters to get wrong — the scoping is a join on the server, so there
 * is no version of this screen that could ask for someone else's work. */

export default function MyWork() {
  const [requests, setRequests] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.myRequests().then(setRequests).catch((err) => setError(err.message))
  }, [])

  if (error) return <div className="error"><AlertCircleIcon size={16} /><span>{error}</span></div>
  if (!requests) return <p className="muted">Loading…</p>

  const open = requests.filter((r) => r.status !== 'resolved')
  const done = requests.filter((r) => r.status === 'resolved')
  const unitCount = new Set(requests.map((r) => r.unit_id)).size

  return (
    <section>
      <div className="page-header">
        <div>
          <h2>My work</h2>
          <p className="muted" style={{ margin: 0 }}>
            Maintenance requests assigned to you across the portfolio
          </p>
        </div>
      </div>

      <div className="grid" style={{ marginBottom: '1.5rem' }}>
        <div className="card" style={{ marginBottom: 0, padding: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="figure">
            <div className="value" style={{ color: open.length > 0 ? 'var(--accent)' : 'var(--muted)' }}>
              {open.length}
            </div>
            <div className="label">Open Work Orders</div>
          </div>
          <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', background: 'var(--accent-light)', color: 'var(--accent)', border: '1px solid var(--accent)', boxShadow: '0 0 10px var(--accent-light)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <RequestIcon size={20} />
          </div>
        </div>

        <div className="card" style={{ marginBottom: 0, padding: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="figure">
            <div className="value" style={{ color: 'var(--good)' }}>{done.length}</div>
            <div className="label">Resolved Jobs</div>
          </div>
          <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', background: 'var(--good-light)', color: 'var(--good)', border: '1px solid var(--good)', boxShadow: '0 0 10px var(--good-light)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckCircleIcon size={20} />
          </div>
        </div>

        <div className="card" style={{ marginBottom: 0, padding: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="figure">
            <div className="value" style={{ color: 'var(--ink)' }}>{unitCount}</div>
            <div className="label">Units Assigned</div>
          </div>
          <div style={{ width: '40px', height: '40px', borderRadius: 'var(--radius-md)', background: 'var(--purple-light)', color: 'var(--purple)', border: '1px solid var(--purple)', boxShadow: '0 0 10px var(--purple-light)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <UnitIcon size={20} />
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden', marginBottom: '1.5rem' }}>
        <div style={{ padding: '0.85rem 1.25rem', background: 'var(--surface-alt)', borderBottom: '1px solid var(--line)' }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem' }}>Active Work Orders ({open.length})</h3>
        </div>
        <Table rows={open} empty="Nothing open. You are all caught up!" />
      </div>

      {done.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '0.85rem 1.25rem', background: 'var(--surface-alt)', borderBottom: '1px solid var(--line)' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem' }}>Completed Jobs ({done.length})</h3>
          </div>
          <Table rows={done} empty="" />
        </div>
      )}
    </section>
  )
}

function Table({ rows, empty }) {
  if (rows.length === 0) {
    return (
      <div style={{ padding: '2.5rem 1.5rem', textAlign: 'center' }}>
        <p className="muted" style={{ margin: 0 }}>{empty}</p>
      </div>
    )
  }

  return (
    <div className="table-wrap" style={{ margin: 0, border: 'none', borderRadius: 0 }}>
      <table>
        <thead>
          <tr>
            <th style={{ width: '80px' }}>ID</th>
            <th>Description</th>
            <th style={{ width: '110px' }}>Priority</th>
            <th style={{ width: '120px' }}>Status</th>
            <th>Raised</th>
            <th style={{ width: '40px' }} />
          </tr>
        </thead>
        <tbody>
          {rows.map((request) => (
            <tr key={request.id}>
              <td style={{ fontWeight: 600, color: 'var(--muted)' }}>#{request.id}</td>
              <td>
                <Link to={`/requests/${request.id}`} style={{ fontWeight: 600 }}>
                  {request.description}
                </Link>
              </td>
              <td><span className={`tag ${request.priority}`}>{request.priority}</span></td>
              <td><span className={`tag ${request.status}`}>{request.status}</span></td>
              <td className="muted" style={{ fontSize: '0.825rem' }}>{dateTime(request.created_at)}</td>
              <td>
                <Link to={`/requests/${request.id}`} style={{ display: 'inline-flex', color: 'var(--muted)' }}>
                  <ChevronRightIcon size={16} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
