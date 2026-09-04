import { useState } from 'react'
import { api } from '../api/client.js'
import { BuildingIcon, AlertCircleIcon, UserIcon } from '../components/Icons.jsx'

export default function Login({ onSignedIn }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function handleLogin(e, p) {
    const targetEmail = e ?? email
    const targetPass = p ?? password
    setBusy(true)
    setError(null)
    try {
      onSignedIn(await api.login(targetEmail, targetPass))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function submit(event) {
    event.preventDefault()
    handleLogin()
  }

  function fillDemo(demoEmail, demoPassword) {
    setEmail(demoEmail)
    setPassword(demoPassword)
    handleLogin(demoEmail, demoPassword)
  }

  return (
    <div style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '26rem', padding: '2.25rem', boxShadow: 'var(--shadow-lg)', border: '1px solid var(--accent-border)' }}>
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, var(--accent), var(--purple))',
              color: '#030712',
              marginBottom: '1rem',
              boxShadow: '0 0 20px rgba(0, 242, 254, 0.45)',
            }}
          >
            <BuildingIcon size={26} />
          </div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 0.35rem', letterSpacing: '-0.02em', color: 'var(--ink)' }}>
            Sign in
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: '0.875rem' }}>
            Property Rental & Maintenance Management
          </p>
        </div>

        <form onSubmit={submit}>
          <label>
            <span>Email address</span>
            <input
              type="email"
              placeholder="e.g. priya@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              style={{ maxWidth: '100%' }}
            />
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              style={{ maxWidth: '100%' }}
            />
          </label>

          {error && (
            <div className="error" style={{ marginBottom: '1rem' }}>
              <AlertCircleIcon size={16} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="primary"
            disabled={busy}
            style={{ width: '100%', padding: '0.7rem', marginTop: '0.5rem' }}
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div style={{ marginTop: '1.75rem', paddingTop: '1.25rem', borderTop: '1px solid var(--line)' }}>
          <p className="muted" style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.65rem' }}>
            Quick Demo Accounts
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
            <button
              type="button"
              disabled={busy}
              onClick={() => fillDemo('priya@example.com', 'manager123')}
              style={{ fontSize: '0.8rem', padding: '0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.15rem' }}
            >
              <span style={{ fontWeight: 600 }}>Priya</span>
              <span className="muted" style={{ fontSize: '0.7rem' }}>Manager</span>
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => fillDemo('tomas@example.com', 'worker123')}
              style={{ fontSize: '0.8rem', padding: '0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.15rem' }}
            >
              <span style={{ fontWeight: 600 }}>Tomas</span>
              <span className="muted" style={{ fontSize: '0.7rem' }}>Contractor</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
