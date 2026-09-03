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
import RentRoll, { parsePaste } from '../src/pages/RentRoll.jsx'
import Alerts from '../src/pages/Alerts.jsx'
import UnitDetail from '../src/pages/UnitDetail.jsx'
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

const MANAGER = { id: 1, name: 'Priya Nair', role: 'manager' }
const CONTRACTOR = { id: 4, name: 'Tomas Vidal', role: 'contractor' }

check('Units renders its loading state', () => renderToString(<Units user={MANAGER} />))

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

/* --- the rent, alerts and unit screens ------------------------------------------------------ */

check('Units offers a manager the create control and a contractor none', () => {
  const manager = at('/units', <Units user={MANAGER} />)
  if (!manager.includes('Add a unit')) throw new Error('manager cannot add a unit')
  const contractor = at('/units', <Units user={CONTRACTOR} />)
  if (contractor.includes('Add a unit')) throw new Error('contractor offered the create control')
  // Requirement 1: the rent column is absent for a contractor because the API omits the field.
  if (contractor.includes('Rent now')) throw new Error('rent column shown to a contractor')
})

check('RentRoll renders with its paste box and CSV link', () => {
  const html = at('/rent', <RentRoll />)
  if (!html.includes('href="/api/rent/roll.csv')) throw new Error('no CSV export link')
  if (!html.includes('textarea')) throw new Error('no paste box')
})

check('the paste parser reads the three separators, and refuses what it cannot read', () => {
  // Reaches into the module rather than the DOM: the parse is the only judgement this screen
  // makes, and getting it wrong is the one way a pasted line could vanish silently.
  const good = parsePaste('4B, 1200.00\n5A 1350\n6C;900.5\n\n')
  if (good.rows.length !== 3) throw new Error('read ' + good.rows.length + ' of 3 rows')
  if (good.problems.length) throw new Error('clean paste reported problems')
  if (good.rows[0].unit_number !== '4B' || good.rows[0].amount !== '1200.00') {
    throw new Error('bad first row: ' + JSON.stringify(good.rows[0]))
  }
  const bad = parsePaste('4B\n5A, 0\n6C, 900')
  if (bad.rows.length !== 1) throw new Error('kept ' + bad.rows.length + ' rows, expected 1')
  if (bad.problems.length !== 2) throw new Error('found ' + bad.problems.length + ' problems, expected 2')
  if (bad.problems[0].line !== 1 || bad.problems[1].line !== 2) throw new Error('wrong line numbers')
})

check('Alerts renders its loading state', () => at('/alerts', <Alerts />))

check('UnitDetail renders its loading state for both roles', () => {
  at('/units/1', <UnitDetail user={MANAGER} />)
  at('/units/1', <UnitDetail user={CONTRACTOR} />)
})

check('every priority and status has a tag colour', () => {
  // Read by path rather than by import.meta.url: this is bundled to CJS, where that is absent.
  // `npm run check` runs from web/, so the relative path is stable.
  const css = readFileSync('src/index.css', 'utf8')
  // Every value the API can send, so a state cannot arrive with no styling and read as plain
  // text beside its neighbours. The bulk outcomes are here too — they use the same tag.
  const states = ['urgent', 'high', 'matched', 'overpaid', 'partial', 'unpaid', 'resolved',
                  'scheduled', 'not_due', 'overdue', 'underpaid', 'unmatched']
  for (const name of states) {
    if (!css.includes('.tag.' + name)) throw new Error('no .tag.' + name + ' rule')
  }
})


if (problems.length) { console.log('\n' + problems.length + ' FAILED'); process.exit(1) }
console.log('\nall render checks passed')
