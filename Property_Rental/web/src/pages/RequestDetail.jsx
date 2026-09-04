import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client.js'
import { dateTime } from '../format.js'
import {
  AlertCircleIcon,
  CheckCircleIcon,
  ClockIcon,
  NoteIcon,
  UserIcon,
  PlusIcon,
  ChevronRightIcon,
  RequestIcon,
} from '../components/Icons.jsx'

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
const STAGES = ['reported', 'triaged', 'scheduled', 'resolved']

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

  if (error && !request) return <div className="error"><AlertCircleIcon size={16} /><span>{error}</span></div>
  if (!request) return <p className="muted">Loading…</p>

  const assignedIds = new Set(request.contractors.map((c) => c.id))
  const available = contractors.filter((c) => !assignedIds.has(c.id))

  const currentStageIndex = STAGES.indexOf(request.status)

  return (
    <section>
      <div style={{ marginBottom: '1rem' }}>
        <Link to="/requests" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.875rem' }}>
          ← All requests
        </Link>
      </div>

      <div className="page-header" style={{ alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <h2>Request #{request.id}</h2>
            <span className={`tag ${request.status}`}>{request.status}</span>
            <span className={`tag ${request.priority}`}>{request.priority}</span>
          </div>
          <p className="muted" style={{ margin: '0.25rem 0 0' }}>
            Unit <Link to="/units" style={{ fontWeight: 600 }}>#{request.unit_id}</Link> · raised {dateTime(request.created_at)}
            {request.resolved_at && ` · resolved ${dateTime(request.resolved_at)}`}
          </p>
        </div>
      </div>

      {error && (
        <div className="error">
          <AlertCircleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Visual Lifecycle Stepper */}
      <div className="lifecycle-stepper">
        {STAGES.map((stage, idx) => {
          const isPassed = idx < currentStageIndex
          const isActive = idx === currentStageIndex
          return (
            <div key={stage} style={{ display: 'flex', alignItems: 'center', flex: idx === STAGES.length - 1 ? 0 : 1 }}>
              <div className={`stepper-step ${isActive ? 'active' : ''} ${isPassed ? 'passed' : ''}`}>
                <div className="stepper-circle">
                  {isPassed ? '✓' : idx + 1}
                </div>
                <span style={{ textTransform: 'capitalize' }}>{stage}</span>
              </div>
              {idx < STAGES.length - 1 && <div className="stepper-divider" />}
            </div>
          )
        })}
      </div>

      {/* Details Card */}
      <div className="card">
        {editing ? (
          <Edit request={request} onDone={() => { setEditing(false); load() }} onError={setError} />
        ) : (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
              <div style={{ flex: 1 }}>
                <h3 style={{ fontSize: '0.85rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.35rem' }}>
                  Issue Description
                </h3>
                <p style={{ margin: 0, fontSize: '1.05rem', lineHeight: 1.5, color: 'var(--ink)' }}>
                  {request.description}
                </p>
              </div>
              <button onClick={() => setEditing(true)} style={{ flexShrink: 0 }}>
                Edit description and priority
              </button>
            </div>
          </>
        )}
      </div>

      {/* Workflow Transition Card */}
      <div className="card">
        <h3 style={{ margin: '0 0 0.5rem' }}>Workflow Actions</h3>
        <div className="row" style={{ alignItems: 'center' }}>
          {(NEXT[request.status] ?? []).map((next) => (
            <button
              key={next}
              className="primary"
              disabled={busy}
              onClick={() => act(() => api.changeStatus(request.id, next))}
              style={{ minWidth: '120px' }}
            >
              {request.status === 'resolved' ? 'Reopen (back to Triaged)' : VERB[next]}
            </button>
          ))}
          {request.status === 'triaged' && request.contractors.length === 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--warn)', fontSize: '0.825rem' }}>
              <AlertCircleIcon size={16} />
              <span>Scheduling requires at least one assigned contractor first.</span>
            </div>
          )}
        </div>
      </div>

      {/* Contractors Card */}
      <div className="card">
        <h3 style={{ margin: '0 0 0.75rem' }}>Assigned Contractors</h3>
        {request.contractors.length === 0 ? (
          <p className="muted" style={{ margin: '0 0 1rem' }}>Nobody is assigned yet.</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.65rem', marginBottom: '1rem' }}>
            {request.contractors.map((c) => {
              const initial = c.name ? c.name.charAt(0).toUpperCase() : 'C'
              return (
                <div
                  key={c.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    background: 'var(--surface-alt)',
                    padding: '0.4rem 0.75rem',
                    borderRadius: '999px',
                    border: '1px solid var(--line)',
                  }}
                >
                  <div className="user-avatar" style={{ width: '22px', height: '22px', fontSize: '0.7rem' }}>{initial}</div>
                  <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>{c.name}</span>
                  {user.role === 'manager' && (
                    <button
                      className="subtle"
                      disabled={busy}
                      onClick={() => act(() => api.unassign(request.id, c.id))}
                      style={{ padding: '0 0.25rem', fontSize: '0.75rem', color: 'var(--bad)' }}
                      title="Remove contractor"
                    >
                      ✕
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Manager-only contractor assignment form */}
        {user.role === 'manager' && available.length > 0 && (
          <form
            className="row"
            onSubmit={(event) => {
              event.preventDefault()
              const chosen = new FormData(event.target).get('contractor_id')
              if (chosen) act(() => api.assign(request.id, Number(chosen)))
            }}
            style={{ alignItems: 'flex-end', paddingTop: '0.75rem', borderTop: '1px solid var(--line)' }}
          >
            <label style={{ marginBottom: 0 }}>
              <span>Assign someone</span>
              <select name="contractor_id" defaultValue="" style={{ width: 'auto', minWidth: '13rem' }}>
                <option value="" disabled>Choose a contractor</option>
                {available.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <button type="submit" disabled={busy} className="primary" style={{ height: '38px' }}>
              Assign
            </button>
          </form>
        )}
      </div>

      {/* Immutable Audit Timeline */}
      <div className="card">
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>Audit Timeline</h3>
          <span className="muted" style={{ fontSize: '0.75rem' }}>Immutable append-only record</span>
        </div>

        <div className="timeline-list">
          {request.timeline.map((event) => (
            <div key={event.id} className="timeline-item">
              <div className="timeline-dot" />
              <div className="timeline-header">
                <span className="timeline-actor">{event.actor_name}</span>
                <span>·</span>
                <span>{dateTime(event.created_at)}</span>
              </div>
              <div className="timeline-body">
                {describe(event)}
              </div>
            </div>
          ))}
        </div>

        {/* Note Composer */}
        <form
          style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid var(--line)' }}
          onSubmit={(event) => {
            event.preventDefault()
            if (note.trim()) act(() => api.addNote(request.id, note.trim()).then(() => setNote('')))
          }}
        >
          <label>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <NoteIcon size={15} />
              <span>Leave a note</span>
            </span>
            <textarea
              rows={3}
              placeholder="Add details, updates, or contractor notes to the timeline…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <button type="submit" disabled={busy || !note.trim()}>
            Add note
          </button>
        </form>
      </div>
    </section>
  )
}

function describe(event) {
  switch (event.event_type) {
    case 'created':
      return <span style={{ fontWeight: 600 }}>Request raised</span>
    case 'status_changed':
      return (
        <span>
          Status changed from <span className={`tag ${event.old_value}`}>{event.old_value}</span> to{' '}
          <span className={`tag ${event.new_value}`}>{event.new_value}</span>
        </span>
      )
    case 'assigned':
      return <span>Assigned contractor <strong style={{ color: 'var(--ink)' }}>{event.new_value}</strong></span>
    case 'unassigned':
      return <span>Removed contractor <strong style={{ color: 'var(--ink)' }}>{event.old_value}</strong></span>
    case 'note':
      return <div style={{ whiteSpace: 'pre-wrap' }}>{event.body}</div>
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
        <select value={priority} onChange={(e) => setPriority(e.target.value)} style={{ width: 'auto', minWidth: '10rem' }}>
          {['urgent', 'high', 'medium', 'low'].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </label>
      <div className="row" style={{ marginTop: '0.75rem' }}>
        <button type="submit" className="primary" disabled={busy}>Save</button>
        <button type="button" onClick={onDone} disabled={busy}>Cancel</button>
      </div>
    </form>
  )
}
