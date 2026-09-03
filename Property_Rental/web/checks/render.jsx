/* Render checks for the browser app.
 *
 * Not a test framework — `npm run check` bundles this with esbuild and runs it in node. It renders
 * each screen to a string with stubbed data, which catches what the Vite build cannot: a component
 * that is not a function, a map over undefined, a bad destructure, and the role rule below.
 *
 * It deliberately does not try to test effects or fetches. Those are the API's behaviour, and the
 * API has 281 tests over it; duplicating them here with a mocked `fetch` would test the mock.
 *
 * `react-dom/server.browser` rather than `react-dom/server`, because the node build reaches for
 * `stream` through a dynamic require that esbuild cannot bundle.
 */

import { readFileSync } from 'node:fs'
import { renderToString } from 'react-dom/server.browser'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Layout from '../src/components/Layout.jsx'
import Login from '../src/pages/Login.jsx'
import Units from '../src/pages/Units.jsx'
import Dashboard from '../src/pages/Dashboard.jsx'
import MyWork from '../src/pages/MyWork.jsx'
import Requests from '../src/pages/Requests.jsx'
import RequestDetail from '../src/pages/RequestDetail.jsx'
import { money, shortDate, monthName, dateTime } from '../src/format.js'

const problems = []
function check(name, fn) {
  try { fn(); console.log('  ok   ' + name) }
  catch (e) { problems.push(name); console.log('  FAIL ' + name + ' :: ' + e.message) }
}

check('format.money', () => {
  if (money('1200.00') !== '1,200.00') throw new Error('got ' + money('1200.00'))
  if (money(null) !== '—') throw new Error('null should be a dash')
  if (money('-') !== '—') throw new Error('roll dash should stay a dash')
})
check('format.shortDate', () => {
  if (shortDate('2026-03-02') !== '02 Mar') throw new Error('got ' + shortDate('2026-03-02'))
})
check('format.monthName', () => {
  if (monthName('2026-08-01') !== 'Aug 2026') throw new Error('got ' + monthName('2026-08-01'))
})
check('format.dateTime handles naive UTC', () => {
  if (dateTime('2026-03-04T10:00:00') === '—') throw new Error('should parse')
})

check('Login renders', () => renderToString(<Login onSignedIn={() => {}} />))

check('Layout renders for a manager with a badge', () => {
  const html = renderToString(
    <MemoryRouter>
      <Routes>
        <Route element={<Layout user={{ name: 'Priya', role: 'manager' }} alertCount={4} onSignedOut={() => {}} />}>
          <Route index element={<p>x</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
  if (!html.includes('badge')) throw new Error('badge missing')
  if (!html.includes('>4<')) throw new Error('count not rendered')
  if (!html.includes('Rent')) throw new Error('manager nav missing Rent')
})

check('Layout hides rent nav from a contractor', () => {
  const html = renderToString(
    <MemoryRouter>
      <Routes>
        <Route element={<Layout user={{ name: 'Tomas', role: 'contractor' }} alertCount={0} onSignedOut={() => {}} />}>
          <Route index element={<p>x</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
  // Checked by href, not by label: the page title is "Property Rental", so a substring test for
  // "Rent" matches the heading and passes for the wrong reason.
  if (html.includes('href="/rent"')) throw new Error('contractor can see the rent nav')
  if (html.includes('href="/alerts"')) throw new Error('contractor can see the alerts nav')
  if (!html.includes('My work')) throw new Error('contractor nav missing My work')
})

check('Layout hides a zero badge', () => {
  const html = renderToString(
    <MemoryRouter>
      <Routes>
        <Route element={<Layout user={{ name: 'Priya', role: 'manager' }} alertCount={0} onSignedOut={() => {}} />}>
          <Route index element={<p>x</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
  if (html.includes('class="badge"')) throw new Error('zero badge rendered')
})

check('Dashboard renders its loading state', () => renderToString(<Dashboard />))
check('Units renders its loading state', () => renderToString(<Units />))

const MANAGER = { id: 1, name: 'Priya Nair', role: 'manager' }
const CONTRACTOR = { id: 4, name: 'Tomas Vidal', role: 'contractor' }

function at(path, element) {
  return renderToString(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={path.split('?')[0]} element={element} />
      </Routes>
    </MemoryRouter>,
  )
}

check('Requests list renders for a manager', () => {
  const html = at('/requests', <Requests user={MANAGER} />)
  for (const control of ['Search descriptions', 'Unit', 'Status', 'Priority', 'Contractor', 'Sort']) {
    if (!html.includes(control)) throw new Error('missing control: ' + control)
  }
})

check('Requests list hides the contractor filter from a contractor', () => {
  // Not a security control — the server scopes the list either way — but offering a contractor a
  // filter over other contractors is offering a filter that can only ever return their own rows.
  const html = at('/requests', <Requests user={CONTRACTOR} />)
  if (html.includes('>Contractor<')) throw new Error('contractor filter shown to a contractor')
  if (!html.includes('Search descriptions')) throw new Error('search box missing')
})

check('MyWork renders its loading state', () => at('/', <MyWork />))

check('RequestDetail renders its loading state', () => at('/requests/1', <RequestDetail user={MANAGER} />))

check('every priority and status has a tag colour', () => {
  // Read by path rather than by import.meta.url: this is bundled to CJS, where that is absent.
  // `npm run check` runs from web/, so the relative path is stable.
  const css = readFileSync('src/index.css', 'utf8')
  for (const name of ['urgent', 'high', 'matched', 'overpaid', 'partial', 'unpaid', 'resolved', 'scheduled']) {
    if (!css.includes('.tag.' + name)) throw new Error('no .tag.' + name + ' rule')
  }
})


if (problems.length) { console.log('\n' + problems.length + ' FAILED'); process.exit(1) }
console.log('\nall render checks passed')
