import React, { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client.js'
import {
  BuildingIcon,
  DashboardIcon,
  UnitIcon,
  RequestIcon,
  RentIcon,
  AlertIcon,
  LogoutIcon,
  SunIcon,
  MoonIcon,
} from './Icons.jsx'

/* The shell every signed-in screen sits in.
 *
 * The navigation is built from the viewer's role rather than by hiding links with CSS. That is
 * only half the guard — the server refuses the routes as well, which is the half that matters —
 * but showing a manager-only link to a contractor would be an invitation to a 403. */

export default function Layout({ user, alertCount, onSignedOut }) {
  const [theme, setTheme] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('pms_theme') || 'dark'
    }
    return 'dark'
  })

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme)
    }
  }, [theme])

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    if (typeof window !== 'undefined') {
      localStorage.setItem('pms_theme', next)
    }
  }

  const links = user.role === 'manager'
    ? [
        { to: '/', label: 'Dashboard', end: true, icon: DashboardIcon },
        { to: '/units', label: 'Units', icon: UnitIcon },
        { to: '/requests', label: 'Requests', icon: RequestIcon },
        { to: '/rent', label: 'Rent', icon: RentIcon },
        { to: '/alerts', label: 'Alerts', badge: alertCount, icon: AlertIcon },
      ]
    : [
        { to: '/', label: 'My work', end: true, icon: DashboardIcon },
        { to: '/requests', label: 'All my requests', icon: RequestIcon },
        { to: '/units', label: 'Units', icon: UnitIcon },
      ]

  async function signOut() {
    await api.logout()
    onSignedOut()
  }

  const initial = user?.name ? user.name.charAt(0).toUpperCase() : 'U'

  return (
    <>
      <nav className="nav">
        <div className="nav-brand">
          <div className="nav-brand-icon">
            <BuildingIcon size={20} />
          </div>
          <h1>Property Rental</h1>
        </div>
        <ul>
          {links.map((link) => {
            const Icon = link.icon
            return (
              <li key={link.to}>
                <NavLink to={link.to} end={link.end}>
                  {Icon && <Icon size={16} />}
                  <span>{link.label}</span>
                  {/* Requirement 10: the count is visible in the navigation, not only on the page.
                      Zero is not shown — a badge saying 0 is noise, not information. */}
                  {link.badge > 0 && <span className="badge">{link.badge}</span>}
                </NavLink>
              </li>
            )
          })}
        </ul>
        <div className="who">
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'neon dark'} theme`}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <SunIcon size={17} /> : <MoonIcon size={17} />}
          </button>
          <div className="user-chip">
            <div className="user-avatar">{initial}</div>
            <span style={{ fontWeight: 600, color: 'var(--ink)' }}>{user.name}</span>
            <span className="role-badge">{user.role}</span>
          </div>
          <button className="subtle" onClick={signOut} title="Sign out" style={{ padding: '0.4rem 0.6rem' }}>
            <LogoutIcon size={16} />
            <span>Sign out</span>
          </button>
        </div>
      </nav>
      <main>
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </>
  )
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, errorInfo) {
    console.error('View render error:', error, errorInfo)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="card" style={{ padding: '2.5rem', textAlign: 'center', margin: '2rem auto', maxWidth: '32rem' }}>
          <h3>Unable to display this view</h3>
          <p className="error" style={{ justifyContent: 'center', margin: '1rem 0' }}>
            {this.state.error?.message ?? 'An unexpected error occurred'}
          </p>
          <button className="primary" onClick={() => { this.setState({ hasError: false }); window.location.reload() }}>
            Reload Page
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

