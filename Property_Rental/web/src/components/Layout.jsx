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
} from './Icons.jsx'

/* The shell every signed-in screen sits in.
 *
 * The navigation is built from the viewer's role rather than by hiding links with CSS. That is
 * only half the guard — the server refuses the routes as well, which is the half that matters —
 * but showing a manager-only link to a contractor would be an invitation to a 403. */

export default function Layout({ user, alertCount, onSignedOut }) {
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
        <Outlet />
      </main>
    </>
  )
}
