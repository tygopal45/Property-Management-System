import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client.js'
import { money, monthName } from '../format.js'
import { DownloadIcon, AlertCircleIcon, CheckCircleIcon, CalendarIcon } from '../components/Icons.jsx'

/* Requirement 7 on one screen: the rent roll, its CSV export, and the bulk paste with its
 * four-way report.
 *
 * The table and the CSV come from the same endpoint pair over the same rows, so the file a
 * manager downloads says what the screen said. The export is an ordinary link rather than a
 * fetch — the browser is already good at saving a file, and going through JavaScript would only
 * add a way for the two to differ. */

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
      <div className="page-header">
        <div>
          <h2>Rent & Collections</h2>
          <p className="muted" style={{ margin: 0 }}>
            Monthly rent roll, bulk payment recording and financial reports
          </p>
        </div>
      </div>

      {error && (
        <div className="error">
          <AlertCircleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Control Bar */}
      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div className="row" style={{ alignItems: 'flex-end' }}>
            <label style={{ margin: 0 }}>
              <span>Target Month</span>
              <input
                type="month"
                value={month}
                onChange={(e) => setMonth(e.target.value || thisMonth())}
                style={{ width: 'auto' }}
              />
            </label>
            <label style={{ margin: 0 }}>
              <span>Archived units</span>
              <label style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer', margin: 0, height: '38px' }}>
                <input
                  type="checkbox"
                  checked={includeArchived}
                  onChange={(e) => setIncludeArchived(e.target.checked)}
                  style={{ width: 'auto', marginRight: '0.45rem' }}
                />
                <span style={{ fontSize: '0.85rem' }}>Include archived</span>
              </label>
            </label>
          </div>
          <a
            className="button-link"
            href={api.rentRollCsvUrl({ month: monthDate(month), include_archived: includeArchived })}
            style={{ height: '38px' }}
          >
            <DownloadIcon size={16} />
            <span>Download CSV</span>
          </a>
        </div>
      </div>

      {/* Summary KPI Cards */}
      {totals && (
        <div className="grid" style={{ marginBottom: '1.5rem' }}>
          <div className="card" style={{ marginBottom: 0, padding: '1rem 1.25rem' }}>
            <div className="figure">
              <div className="value" style={{ color: 'var(--ink)' }}>{money(totals.due)}</div>
              <div className="label">Total Rent Due</div>
            </div>
          </div>
          <div className="card" style={{ marginBottom: 0, padding: '1rem 1.25rem' }}>
            <div className="figure">
              <div className="value" style={{ color: 'var(--good)' }}>{money(totals.paid)}</div>
              <div className="label">Total Paid</div>
            </div>
          </div>
          <div className="card" style={{ marginBottom: 0, padding: '1rem 1.25rem' }}>
            <div className="figure">
              <div className="value" style={{ color: totals.outstanding > 0 ? 'var(--bad)' : 'var(--muted)' }}>
                {money(totals.outstanding)}
              </div>
              <div className="label">Outstanding Balance</div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Entry Form */}
      <form className="card" onSubmit={submitBulk} style={{ marginBottom: '1.5rem' }}>
        <div className="row" style={{ justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>Record rent for {monthName(monthDate(month))}</h3>
          <button
            type="button"
            className="subtle"
            style={{ fontSize: '0.8rem' }}
            onClick={() => setPaste('4B, 1200.00\n5A 1350\n6C;900.50')}
          >
            Fill sample batch
          </button>
        </div>
        <p className="muted" style={{ fontSize: '0.85rem' }}>
          Paste batch payments (one unit per line, as <code>unit, amount</code>). Comma, space or semicolon separators are supported.
          Each row is classified against that unit's rent.
        </p>
        <textarea
          rows={5}
          value={paste}
          onChange={(e) => setPaste(e.target.value)}
          placeholder={'4B, 1200.00\n5A 1350\n6C;900.50'}
        />
        {problems.length > 0 && (
          <div className="error" style={{ display: 'block', marginTop: '0.75rem' }}>
            <p style={{ margin: '0 0 0.4rem', fontWeight: 600 }}>
              {problems.length === 1 ? 'One line' : `${problems.length} lines`} cannot be parsed:
            </p>
            <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
              {problems.map((problem) => (
                <li key={problem.line}>
                  Line {problem.line}: <code>{problem.text}</code> — {problem.why}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="row" style={{ marginTop: '0.85rem' }}>
          <button className="primary" disabled={busy || !parsed.length || problems.length > 0}>
            {busy ? 'Recording…' : `Record ${parsed.length || 'no'} row${parsed.length === 1 ? '' : 's'}`}
          </button>
          {paste && <button type="button" onClick={() => setPaste('')}>Clear</button>}
        </div>
      </form>

      {report && <BulkReport report={report} onClose={() => setReport(null)} />}

      {/* Rent Roll Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '0.85rem 1.25rem', background: '#f8fafc', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem' }}>
            Rent roll — {monthName(monthDate(month))}
          </h3>
        </div>

        {!rows ? (
          <p className="muted" style={{ padding: '1.5rem' }}>Loading…</p>
        ) : rows.length === 0 ? (
          <div style={{ padding: '3rem 1.5rem', textAlign: 'center' }}>
            <p className="muted" style={{ margin: 0 }}>No units to show for this month.</p>
          </div>
        ) : (
          <div className="table-wrap" style={{ margin: 0, border: 'none', borderRadius: 0 }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '120px' }}>Unit</th>
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
                      <Link to={`/units/${row.unit_id}`} style={{ fontWeight: 700 }}>
                        {row.unit_number}
                      </Link>
                      <div className="muted" style={{ fontSize: '0.75rem' }}>{row.address}</div>
                    </td>
                    <td style={{ fontWeight: 500 }}>{row.tenant_name}</td>
                    <td className="num" style={{ fontWeight: 600 }}>
                      {row.status === 'not_due' ? '—' : money(row.monthly_rent)}
                    </td>
                    <td className="num" style={{ color: Number(row.amount_paid) > 0 ? 'var(--good)' : 'var(--muted)' }}>
                      {money(row.amount_paid)}
                    </td>
                    <td className="num" style={{ color: Number(row.outstanding) > 0 ? 'var(--bad)' : 'var(--muted)', fontWeight: 600 }}>
                      {money(row.outstanding)}
                    </td>
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
          </div>
        )}
      </div>
    </section>
  )
}

function BulkReport({ report, onClose }) {
  const { summary } = report
  return (
    <div className="card" style={{ border: '2px solid var(--accent)', marginBottom: '1.5rem' }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: 'var(--accent)' }}>
          Recorded for {monthName(report.period_month)}
        </h3>
        <button onClick={onClose} style={{ fontSize: '0.8rem' }}>Dismiss report</button>
      </div>

      <div className="grid" style={{ margin: '1rem 0' }}>
        <div className="card" style={{ padding: '0.75rem 1rem', marginBottom: 0, background: '#ecfdf5', borderColor: '#a7f3d0' }}>
          <div className="figure">
            <div className="value" style={{ color: 'var(--good)', fontSize: '1.75rem' }}>{summary.matched}</div>
            <div className="label" style={{ color: '#065f46' }}>matched</div>
          </div>
        </div>
        <div className="card" style={{ padding: '0.75rem 1rem', marginBottom: 0, background: '#fffbeb', borderColor: '#fde68a' }}>
          <div className="figure">
            <div className="value" style={{ color: 'var(--warn)', fontSize: '1.75rem' }}>{summary.underpaid}</div>
            <div className="label" style={{ color: '#92400e' }}>underpaid</div>
          </div>
        </div>
        <div className="card" style={{ padding: '0.75rem 1rem', marginBottom: 0, background: '#eff6ff', borderColor: '#bfdbfe' }}>
          <div className="figure">
            <div className="value" style={{ color: 'var(--accent)', fontSize: '1.75rem' }}>{summary.overpaid}</div>
            <div className="label" style={{ color: '#1e40af' }}>overpaid</div>
          </div>
        </div>
        <div className="card" style={{ padding: '0.75rem 1rem', marginBottom: 0, background: '#f1f5f9', borderColor: '#cbd5e1' }}>
          <div className="figure">
            <div className="value" style={{ color: 'var(--muted)', fontSize: '1.75rem' }}>{summary.unmatched}</div>
            <div className="label">unmatched</div>
          </div>
        </div>
      </div>

      <p className="muted" style={{ fontSize: '0.875rem' }}>
        {summary.recorded} of {report.results.length} rows recorded a payment, totalling{' '}
        <strong>{money(summary.total_amount)}</strong>. An unmatched row names no unit collecting rent, so it
        records nothing.
      </p>

      <div className="table-wrap">
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
                <td>#{result.row}</td>
                <td style={{ fontWeight: 600 }}>{result.unit_number}</td>
                <td className="num" style={{ fontWeight: 600 }}>{money(result.amount)}</td>
                <td className="num">{result.expected === null ? '—' : money(result.expected)}</td>
                <td><span className={`tag ${result.outcome}`}>{result.outcome}</span></td>
                <td className="muted" style={{ fontSize: '0.8rem' }}>{result.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
