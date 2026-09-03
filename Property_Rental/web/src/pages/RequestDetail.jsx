import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime } from '../format.js'

/* Requirements 3, 4, 5 and 9 on one screen.
 *
 * The status buttons offer only the moves the server allows, from the same table the server uses.
 * That is presentation, not enforcement — the rule lives in `services/lifecycle.py` and this
 * screen would be refused if it asked for anything else. Offering an illegal move and then
 * showing the rejection would be honest but useless; offering it and *not* showing the rejection
 * is the failure worth avoiding, so both are covered: the buttons are narrowed, and a refusal
 * still shows the server's own sentence. */

const NEXT = {
  reported: ['triaged'],
  triaged: ['scheduled'],
  scheduled: ['resolved'],
  resolved: ['triaged'],
}
const VERB = { triaged: 'Triage', scheduled: 'Schedule', resolved: 'Resolve' }

export default function RequestDetail({ user, onChanged }) {
  const { id } = useParams()
  const [request, setRequest] = useState(null)
  const [contractors, setContractors] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [editing, setEditing] = useState(false)

  const load = useCallback(() => {
    api.requestDetail(id).then(setRequest).catch((err) => setError(err.message))
  }, [id])

  useEffect(load, [load])
  useEffect(() => {
    if (user.role === 'manager') api.contractors().then(setContractors).catch(() => setContractors([]))
  }, [user.role])

  // Every action goes through here so that one place clears the last error, reloads the request,
  // and shows the server's message when it refuses. A screen that swallows a 409 is worse than
  // one that has no buttons.
  async function act(fn) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      load()
      onChanged?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !request) return <p className="error">{error}</p>
  if (!request) return <p className="muted">Loading…</p>

  const assignedIds = new Set(request.contractors.map((c) => c.id))
  const available = contractors.filter((c) => !assignedIds.has(c.id))

  return (
    <section>
      <p className="muted"><Link to="/requests">← All requests</Link></p>
      <h2>
        Request #{request.id}{' '}
        <span className={`tag ${request.status}`}>{request.status}</span>{' '}
        <span className={`tag ${request.priority}`}>{request.priority}</span>
      </h2>

      {error && <p className="error">{error}</p>}

      <div className="card">
        {editing ? (
          <Edit request={request} onDone={() => { setEditing(false); load() }} onError={setError} />
        ) : (
          <>
            <p style={{ marginTop: 0 }}>{request.description}</p>
            <p className="muted">
              Unit <Link to={`/units`}>#{request.unit_id}</Link> · raised {dateTime(request.created_at)}
              {request.resolved_at && ` · resolved ${dateTime(request.resolved_at)}`}
            </p>
            {/* Requirement 3: either role edits the description and priority. The assignment
                list is not on this form, and not on the API's payload either. */}
            <button onClick={() => setEditing(true)}>Edit description and priority</button>
          </>
        )}
      </div>

      <div className="card">
        <h3>Move it on</h3>
        <div className="row">
          {(NEXT[request.status] ?? []).map((next) => (
            <button
              key={next}
              className="primary"
              disabled={busy}
              onClick={() => act(() => api.changeStatus(request.id, next))}
            >
              {request.status === 'resolved' ? 'Reopen (back to Triaged)' : VERB[next]}
            </button>
          ))}
        </div>
        {request.status === 'triaged' && request.contractors.length === 0 && (
          <p className="muted">
            Scheduling needs a contractor assigned first — the server refuses it otherwise.
          </p>
        )}
      </div>

      <div className="card">
        <h3>Contractors</h3>
        {request.contractors.length === 0 && <p className="muted">Nobody is assigned yet.</p>}
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {request.contractors.map((c) => (
            <li key={c.id} className="row" style={{ alignItems: 'center', marginBottom: '0.4rem' }}>
              <span>{c.name}</span>
              {user.role === 'manager' && (
                <button disabled={busy} onClick={() => act(() => api.unassign(request.id, c.id))}>
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>

        {/* Requirement 5: only a manager assigns. A contractor sees the list and no controls —
            and the server refuses them regardless, which is the half that counts. */}
        {user.role === 'manager' && available.length > 0 && (
          <form
            className="row"
            onSubmit={(event) => {
              event.preventDefault()
              const chosen = new FormData(event.target).get('contractor_id')
              if (chosen) act(() => api.assign(request.id, Number(chosen)))
            }}
          >
            <label style={{ marginBottom: 0 }}>
              <span>Assign someone</span>
              <select name="contractor_id" defaultValue="">
                <option value="" disabled>Choose a contractor</option>
                {available.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <button type="submit" disabled={busy}>Assign</button>
          </form>
        )}
      </div>

      <div className="card">
        <h3>Timeline</h3>
        {/* Requirement 9. Read-only because there is nothing else it could be: no route exists
            that edits or deletes an event, for any role. */}
        <table>
          <tbody>
            {request.timeline.map((event) => (
              <tr key={event.id}>
                <td className="muted" style={{ whiteSpace: 'nowrap' }}>{dateTime(event.created_at)}</td>
                <td>{describe(event)}</td>
                <td className="muted">{event.actor_name}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <form
          style={{ marginTop: '1rem' }}
          onSubmit={(event) => {
            event.preventDefault()
            if (note.trim()) act(() => api.addNote(request.id, note.trim()).then(() => setNote('')))
          }}
        >
          <label>
            <span>Leave a note</span>
            <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <button type="submit" disabled={busy || !note.trim()}>Add note</button>
        </form>
      </div>
    </section>
  )
}

function describe(event) {
  switch (event.event_type) {
    case 'created':
      return 'Request raised'
    case 'status_changed':
      return <>Status <span className={`tag ${event.old_value}`}>{event.old_value}</span> → <span className={`tag ${event.new_value}`}>{event.new_value}</span></>
    case 'assigned':
      return `Assigned ${event.new_value}`
    case 'unassigned':
      return `Removed ${event.old_value}`
    case 'note':
      return event.body
    default:
      return event.event_type
  }
}

function Edit({ request, onDone, onError }) {
  const [description, setDescription] = useState(request.description)
  const [priority, setPriority] = useState(request.priority)
  const [busy, setBusy] = useState(false)

  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault()
        setBusy(true)
        try {
          await api.updateRequest(request.id, { description, priority })
          onDone()
        } catch (err) {
          onError(err.message)
        } finally {
          setBusy(false)
        }
      }}
    >
      <label>
        <span>Description</span>
        <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} required />
      </label>
      <label>
        <span>Priority</span>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          {['urgent', 'high', 'medium', 'low'].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
      <div className="row">
        <button type="submit" className="primary" disabled={busy}>Save</button>
        <button type="button" onClick={onDone}>Cancel</button>
      </div>
    </form>
  )
}
