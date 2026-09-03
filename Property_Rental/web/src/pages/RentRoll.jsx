import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { money, monthName } from '../format.js'

/* Requirement 7 on one screen: the rent roll, its CSV export, and the bulk paste with its
 * four-way report.
 *
 * The table and the CSV come from the same endpoint pair over the same rows, so the file a
 * manager downloads says what the screen said. The export is an ordinary link rather than a
 * fetch — the browser is already good at saving a file, and going through JavaScript would only
 * add a way for the two to differ. */

// A month input gives "2026-09"; every month-shaped date in this system is the 1st (schema.md §7).
function monthValue(iso) {
  return iso.slice(0, 7)
}
function monthDate(value) {
  return `${value}-01`
}
function thisMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

/* Reading the pasted text is presentation, not judgement. This splits lines into a unit and an
 * amount and nothing more — whether an amount matches the rent is the server's answer, and
 * deciding it here as well would be a second opinion that could disagree with the receipt.
 *
 * A line it cannot read becomes a problem rather than a skipped row. Dropping it quietly would
 * be the worst outcome available: the manager would read "12 recorded" and believe the
 * thirteenth line went in. */
const LINE = /^(.+?)[\s,;]+([0-9]+(?:\.[0-9]{1,2})?)$/

// Exported for the render check: the parse is the only judgement this screen makes on its own.
export function parsePaste(text) {
  const rows = []
  const problems = []
  text.split('\n').forEach((raw, index) => {
    const line = raw.trim()
    if (!line) return
    const found = LINE.exec(line)
    if (!found) {
      problems.push({ line: index + 1, text: line, why: 'expected a unit and an amount' })
      return
    }
    const amount = found[2]
    if (Number(amount) <= 0) {
      problems.push({ line: index + 1, text: line, why: 'the amount must be more than zero' })
      return
    }
    rows.push({ unit_number: found[1].trim(), amount })
  })
  return { rows, problems }
}

export default function RentRoll({ onChanged }) {
  const [month, setMonth] = useState(thisMonth)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  const [paste, setPaste] = useState('')
  const [report, setReport] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setRows(null)
    api
      .rentRoll({ month: monthDate(month), include_archived: includeArchived })
      .then(setRows)
      .catch((err) => setError(err.message))
  }, [month, includeArchived])

  useEffect(load, [load])

  const { rows: parsed, problems } = parsePaste(paste)

  async function submitBulk(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await api.bulkRent({ period_month: monthDate(month), rows: parsed })
      setReport(result)
      setPaste('')
      // Recording rent can settle an alert, so the badge is asked again rather than left to rot.
      load()
      onChanged?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const totals = rows && {
    due: rows.reduce((sum, row) => sum + Number(row.monthly_rent), 0),
    paid: rows.reduce((sum, row) => sum + Number(row.amount_paid), 0),
    outstanding: rows.reduce((sum, row) => sum + Number(row.outstanding), 0),
  }

  return (
    <section>
      <h2>Rent</h2>

      <div className="card">
        <div className="row">
          <label style={{ margin: 0 }}>
            <span>Month</span>
            <input type="month" value={month} onChange={(e) => setMonth(e.target.value || thisMonth())} />
          </label>
          <label style={{ margin: 0 }}>
            <span>Archived units</span>
            <span>
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={(e) => setIncludeArchived(e.target.checked)}
                style={{ width: 'auto', marginRight: '0.4rem' }}
              />
              Include
            </span>
          </label>
          <a
            className="button-link"
            href={api.rentRollCsvUrl({ month: monthDate(month), include_archived: includeArchived })}
          >
            Download CSV
          </a>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {/* --- the paste box: requirement 7's bulk entry --------------------------------------- */}
      <form className="card" onSubmit={submitBulk}>
        <h3>Record rent for {monthName(monthDate(month))}</h3>
        <p className="muted">
          One unit per line, as <code>unit, amount</code> — a comma, a space or a semicolon all
          read the same. Every row is judged against that unit's own rent for this month and gets
          its own line in the report below.
        </p>
        <textarea
          rows={6}
          value={paste}
          onChange={(e) => setPaste(e.target.value)}
          placeholder={'4B, 1200.00\n5A 1350\n6C;900.50'}
        />
        {problems.length > 0 && (
          <div className="error">
            <p style={{ marginBottom: '0.25rem' }}>
              {problems.length === 1 ? 'One line' : `${problems.length} lines`} cannot be read.
              Nothing is sent until they are fixed or removed — a line dropped quietly would look
              like a line that was recorded.
            </p>
            <ul style={{ margin: 0 }}>
              {problems.map((problem) => (
                <li key={problem.line}>
                  Line {problem.line}: <code>{problem.text}</code> — {problem.why}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="row" style={{ marginTop: '0.75rem' }}>
          <button className="primary" disabled={busy || !parsed.length || problems.length > 0}>
            {busy ? 'Recording…' : `Record ${parsed.length || 'no'} row${parsed.length === 1 ? '' : 's'}`}
          </button>
          {paste && <button type="button" onClick={() => setPaste('')}>Clear</button>}
        </div>
      </form>

      {report && <BulkReport report={report} onClose={() => setReport(null)} />}

      {/* --- the roll ----------------------------------------------------------------------- */}
      <h3>Rent roll — {monthName(monthDate(month))}</h3>
      {!rows ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No units to show for this month.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Unit</th>
              <th>Tenant</th>
              <th className="num">Rent</th>
              <th className="num">Paid</th>
              <th className="num">Outstanding</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.unit_id}>
                <td>
                  <Link to={`/units/${row.unit_id}`}>{row.unit_number}</Link>
                  <div className="muted">{row.address}</div>
                </td>
                <td>{row.tenant_name}</td>
                {/* not_due carries no figure: nothing is owed before a unit's first rent or after
                    it is archived, and printing 0.00 would read as a rent of nothing. */}
                <td className="num">{row.status === 'not_due' ? '—' : money(row.monthly_rent)}</td>
                <td className="num">{money(row.amount_paid)}</td>
                <td className="num">{money(row.outstanding)}</td>
                <td>
                  <span className={`tag ${row.status}`}>{row.status.replace('_', ' ')}</span>
                  {row.overdue && <> <span className="tag overdue">overdue</span></>}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th colSpan={2}>{rows.length} units</th>
              <th className="num">{money(totals.due)}</th>
              <th className="num">{money(totals.paid)}</th>
              <th className="num">{money(totals.outstanding)}</th>
              <th />
            </tr>
          </tfoot>
        </table>
      )}
    </section>
  )
}

/* The four-way report. The counts come from the server rather than being tallied here, so the
 * summary a manager reads is the same number the API stands behind. */
function BulkReport({ report, onClose }) {
  const { summary } = report
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3 style={{ margin: 0 }}>Recorded for {monthName(report.period_month)}</h3>
        <button onClick={onClose}>Dismiss report</button>
      </div>
      <div className="grid" style={{ marginTop: '0.75rem' }}>
        <div className="figure"><div className="value">{summary.matched}</div><div className="label">matched</div></div>
        <div className="figure"><div className="value">{summary.underpaid}</div><div className="label">underpaid</div></div>
        <div className="figure"><div className="value">{summary.overpaid}</div><div className="label">overpaid</div></div>
        <div className="figure"><div className="value">{summary.unmatched}</div><div className="label">unmatched</div></div>
      </div>
      <p className="muted">
        {summary.recorded} of {report.results.length} rows recorded a payment, totalling{' '}
        {money(summary.total_amount)}. An unmatched row names no unit collecting rent, so it
        records nothing — and the total counts only what actually went in.
      </p>
      <table>
        <thead>
          <tr>
            <th>Line</th>
            <th>Unit</th>
            <th className="num">Amount</th>
            <th className="num">Expected</th>
            <th>Outcome</th>
            <th>Why</th>
          </tr>
        </thead>
        <tbody>
          {report.results.map((result) => (
            <tr key={result.row}>
              <td>{result.row}</td>
              <td>{result.unit_number}</td>
              <td className="num">{money(result.amount)}</td>
              <td className="num">{result.expected === null ? '—' : money(result.expected)}</td>
              <td><span className={`tag ${result.outcome}`}>{result.outcome}</span></td>
              {/* The server writes a sentence for every row saying why it landed where it did.
                  Showing it is the whole point of requirement 7's report. */}
              <td className="muted">{result.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
