import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

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
  const navigate = useNavigate()
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
        <>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {definitions.map(([key, label, description]) => (
            <section className="card" key={key}>
              <p className="text-3xl font-bold text-indigo-600">{stats.stats[key]}</p>
              <h3 className="mt-3 font-semibold">{label}</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
            </section>
          ))}
        </div>
        <div className="mt-7 grid gap-5 lg:grid-cols-2">
          <section className="card">
            <div className="flex items-baseline justify-between gap-3"><h3 className="text-lg font-semibold">Recent important emails</h3><button className="text-sm font-semibold text-indigo-700 hover:underline" type="button" onClick={() => navigate('/inbox')}>Open inbox</button></div>
            {stats.recent_important.length ? <div className="mt-4 divide-y">{stats.recent_important.map((email) => <button className="block w-full py-3 text-left first:pt-0 last:pb-0" type="button" key={email.id} onClick={() => navigate(`/inbox?email=${email.id}`)}><div className="flex items-start justify-between gap-3"><span className="truncate font-semibold">{email.subject}</span><span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${email.priority === 'urgent' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-800'}`}>{email.priority}</span></div><p className="mt-1 truncate text-xs text-slate-500">{email.sender}</p><p className="mt-2 line-clamp-2 text-sm text-slate-600">{email.summary}</p></button>)}</div> : <p className="mt-4 text-sm text-slate-500">No high-priority emails yet. Sync Gmail or load demo data.</p>}
          </section>
          <section className="card">
            <div className="flex items-baseline justify-between gap-3"><h3 className="text-lg font-semibold">Upcoming deadlines</h3><button className="text-sm font-semibold text-indigo-700 hover:underline" type="button" onClick={() => navigate('/tasks')}>Open tasks</button></div>
            {stats.upcoming_deadlines.length ? <div className="mt-4 divide-y">{stats.upcoming_deadlines.map((task) => <button className="block w-full py-3 text-left first:pt-0 last:pb-0" type="button" key={task.id} onClick={() => navigate(`/inbox?email=${task.email_id}`)}><div className="flex items-start justify-between gap-3"><span className="truncate font-semibold">{task.title}</span><span className="shrink-0 text-xs font-semibold text-indigo-700">{task.normalized_deadline}</span></div><p className="mt-1 truncate text-xs text-slate-500">{task.source_subject}</p></button>)}</div> : <p className="mt-4 text-sm text-slate-500">No upcoming normalized deadlines found.</p>}
          </section>
        </div>
        </>
      )}
    </div>
  )
}
