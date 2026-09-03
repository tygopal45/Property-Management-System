import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime } from '../format.js'

/* Requirement 5: "every contractor can see one list of every request assigned to them, across
 * every unit." One call, no filters to get wrong — the scoping is a join on the server, so there
 * is no version of this screen that could ask for someone else's work. */

export default function MyWork() {
  const [requests, setRequests] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.myRequests().then(setRequests).catch((err) => setError(err.message))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!requests) return <p className="muted">Loading…</p>

  const open = requests.filter((r) => r.status !== 'resolved')
  const done = requests.filter((r) => r.status === 'resolved')

  return (
    <section>
      <h2>My work</h2>
      <p className="muted">
        {open.length} open · {done.length} resolved · across{' '}
        {new Set(requests.map((r) => r.unit_id)).size} unit(s)
      </p>
      <Table rows={open} empty="Nothing open. " />
      {done.length > 0 && (
        <>
          <h3 style={{ marginTop: '2rem' }}>Resolved</h3>
          <Table rows={done} empty="" />
        </>
      )}
    </section>
  )
}

function Table({ rows, empty }) {
  if (rows.length === 0) return <p className="muted">{empty}</p>
  return (
    <table>
      <thead>
        <tr>
          <th>Description</th><th>Priority</th><th>Status</th><th>Raised</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((request) => (
          <tr key={request.id}>
            <td><Link to={`/requests/${request.id}`}>{request.description}</Link></td>
            <td><span className={`tag ${request.priority}`}>{request.priority}</span></td>
            <td><span className={`tag ${request.status}`}>{request.status}</span></td>
            <td className="muted">{dateTime(request.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
