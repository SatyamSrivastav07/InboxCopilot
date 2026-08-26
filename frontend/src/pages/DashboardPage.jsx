import { useEffect, useState } from 'react'

import { ErrorState, LoadingState } from '../components/PageFeedback.jsx'
import { getDashboardStats } from '../services/api.js'

const definitions = [
  ['total_emails', 'Total Emails', 'Persisted Gmail messages'],
  ['needs_reply', 'Needs Reply', 'Awaiting your response'],
  ['pending_tasks', 'Pending Tasks', 'Extracted actions not completed'],
  ['high_urgent', 'High / Urgent', 'Important inbox items'],
  ['upcoming_meetings', 'Upcoming Meetings', 'Meetings with normalized future dates'],
]

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getDashboardStats().then(setStats).catch((requestError) => setError(requestError.message))
  }, [])

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <div className="mb-7"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Workspace</p><h2 className="mt-1 text-3xl font-semibold">Dashboard</h2><p className="mt-2 text-sm text-slate-500">A live view of your persisted inbox intelligence.</p></div>
      {error && <ErrorState message={error} />}
      {!error && !stats && <LoadingState message="Loading dashboard…" />}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {definitions.map(([key, label, description]) => (
            <section className="card" key={key}>
              <p className="text-3xl font-bold text-indigo-600">{stats[key]}</p>
              <h3 className="mt-3 font-semibold">{label}</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

