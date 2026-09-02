import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

export default function Units() {
  const [units, setUnits] = useState([])
  const [includeArchived, setIncludeArchived] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.units(includeArchived).then(setUnits).catch((err) => setError(err.message))
  }, [includeArchived])

  if (error) return <p className="error">{error}</p>

  return (
    <section>
      <h2>Units</h2>
      <label>
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
          style={{ width: 'auto', marginRight: '0.5rem' }}
        />
        Show archived
      </label>
      <table>
        <thead>
          <tr>
            <th>Unit</th>
            <th>Address</th>
            <th>Tenant</th>
            <th>Rent now</th>
            <th>State</th>
          </tr>
        </thead>
        <tbody>
          {units.map((unit) => (
            <tr key={unit.id}>
              <td>{unit.unit_number}</td>
              <td>{unit.address}</td>
              <td>{unit.tenant_name}</td>
              {/* The rent in force today, worked out from the rent history by the API. */}
              <td>{unit.current_rent ?? '—'}</td>
              <td>{unit.archived_at ? 'Archived' : 'Active'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {units.length === 0 && <p className="muted">No units to show.</p>}
    </section>
  )
}
