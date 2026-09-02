import { useEffect, useState } from 'react'
import { api } from './api/client.js'
import Login from './pages/Login.jsx'
import Units from './pages/Units.jsx'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    // Ask the server who we are. A 401 just means "not signed in", which is not an error.
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
    api.health().then(setHealth).catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  if (loading) return <main>Loading…</main>
  if (!user) return <Login onSignedIn={setUser} />

  return (
    <main>
      <header>
        <h1>Property Rental &amp; Maintenance</h1>
        <p className="muted">
          Signed in as {user.name} ({user.role}){' '}
          <button
            onClick={async () => {
              await api.logout()
              setUser(null)
            }}
          >
            Sign out
          </button>
        </p>
      </header>
      <Units />
      <footer className="muted">
        <p>
          API: {health?.status ?? '…'} · database: {health?.database ?? '…'}
        </p>
      </footer>
    </main>
  )
}
