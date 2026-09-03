import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api/client.js'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Login from './pages/Login.jsx'
import MyWork from './pages/MyWork.jsx'
import RequestDetail from './pages/RequestDetail.jsx'
import Requests from './pages/Requests.jsx'
import Units from './pages/Units.jsx'

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [alertCount, setAlertCount] = useState(0)

  useEffect(() => {
    // Ask the server who we are. A 401 just means "not signed in", which is not an error.
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false))
  }, [])

  // The badge count lives here rather than in the alerts page, because the navigation shows it
  // on every screen. Screens that change it — dismissing an alert, recording rent — call
  // refreshAlerts, so the number cannot sit stale behind the page that just changed it.
  const refreshAlerts = useCallback(() => {
    if (user?.role !== 'manager') return
    api.alerts().then((data) => setAlertCount(data.count)).catch(() => setAlertCount(0))
  }, [user])

  useEffect(() => { refreshAlerts() }, [refreshAlerts])

  if (loading) return <main>Loading…</main>
  if (!user) return <Login onSignedIn={setUser} />

  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <Layout user={user} alertCount={alertCount} onSignedOut={() => setUser(null)} />
          }
        >
          {/* A manager lands on the portfolio dashboard; a contractor lands on their own work.
              Two different jobs, so two different landing views rather than one screen that
              quietly returns less to some callers. */}
          <Route index element={user.role === 'manager' ? <Dashboard /> : <MyWork />} />
          <Route path="units" element={<Units />} />
          <Route path="requests" element={<Requests user={user} />} />
          <Route
            path="requests/:id"
            element={<RequestDetail user={user} onChanged={refreshAlerts} />}
          />
          {/* Anything not built yet lands on the home route rather than on a blank page. */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
