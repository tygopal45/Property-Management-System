// Formatting only. Nothing here decides anything — the API has already worked out every value
// on this side of the wire, and a second opinion in the browser is how the two start disagreeing.

export function money(value) {
  if (value === null || value === undefined || value === '-') return '—'
  // The API sends money as a string so the decimal survives the trip. Number() is for display
  // width only; the value shown is still the two-decimal figure the server sent.
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

export function shortDate(iso) {
  if (!iso) return '—'
  const [year, month, day] = iso.slice(0, 10).split('-')
  return `${day} ${MONTHS[Number(month) - 1]}`
}

export function monthName(iso) {
  if (!iso) return '—'
  const [year, month] = iso.slice(0, 7).split('-')
  return `${MONTHS[Number(month) - 1]} ${year}`
}

export function dateTime(iso) {
  if (!iso) return '—'
  // Timestamps arrive as naive UTC (schema.md §10), so they are marked as UTC before formatting.
  return new Date(`${iso}Z`).toLocaleString()
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
