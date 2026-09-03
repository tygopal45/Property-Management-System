import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client.js'

/* The shell every signed-in screen sits in.
 *
 * The navigation is built from the viewer's role rather than by hiding links with CSS. That is
 * only half the guard — the server refuses the routes as well, which is the half that matters —
 * but showing a manager-only link to a contractor would be an invitation to a 403. */

export default function Layout({ user, alertCount, onSignedOut }) {
  const links = user.role === 'manager'
    ? [
        { to: '/', label: 'Dashboard', end: true },
        { to: '/units', label: 'Units' },
        { to: '/requests', label: 'Requests' },
        { to: '/rent', label: 'Rent' },
        { to: '/alerts', label: 'Alerts', badge: alertCount },
      ]
    : [
        { to: '/', label: 'My work', end: true },
        { to: '/units', label: 'Units' },
      ]

  async function signOut() {
    await api.logout()
    onSignedOut()
  }

  return (
    <>
      <nav className="nav">
        <h1>Property Rental</h1>
        <ul>
          {links.map((link) => (
            <li key={link.to}>
              <NavLink to={link.to} end={link.end}>
                {link.label}
                {/* Requirement 10: the count is visible in the navigation, not only on the page.
                    Zero is not shown — a badge saying 0 is noise, not information. */}
                {link.badge > 0 && <span className="badge">{link.badge}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
        <span className="who">
          {user.name} · {user.role} <button onClick={signOut}>Sign out</button>
        </span>
      </nav>
      <main>
        <Outlet />
      </main>
    </>
  )
}
