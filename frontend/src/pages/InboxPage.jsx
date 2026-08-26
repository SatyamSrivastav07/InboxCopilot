import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ErrorState, LoadingState, NoData } from '../components/PageFeedback.jsx'
import PersistedEmailCard from '../components/PersistedEmailCard.jsx'
import PersistedEmailDetails from '../components/PersistedEmailDetails.jsx'
import { getPersistedEmail, getPersistedEmails } from '../services/api.js'

const categories = ['action_required', 'needs_reply', 'meeting', 'important_update', 'newsletter', 'promotion', 'receipt', 'notification', 'low_value', 'other']

export default function InboxPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [filters, setFilters] = useState({ category: '', priority: '', reply_required: '' })
  const [emails, setEmails] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  const requestedEmailId = searchParams.get('email')

  useEffect(() => {
    setEmails(null)
    setError('')
    const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''))
    getPersistedEmails(params).then(setEmails).catch((requestError) => setError(requestError.message))
  }, [filters])

  useEffect(() => {
    if (!requestedEmailId) return
    getPersistedEmail(requestedEmailId)
      .then(setSelected)
      .catch((requestError) => setError(requestError.message))
  }, [requestedEmailId])

  const viewDetails = async (emailId) => {
    setError('')
    try { setSelected(await getPersistedEmail(emailId)) } catch (requestError) { setError(requestError.message) }
  }

  const updateFilter = (event) => setFilters((current) => ({ ...current, [event.target.name]: event.target.value }))

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <div className="mb-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Database</p><h2 className="mt-1 text-3xl font-semibold">Inbox</h2><p className="mt-2 text-sm text-slate-500">Previously processed Gmail intelligence survives restarts.</p></div>
      <section className="card mb-6 grid gap-4 sm:grid-cols-3">
        <label className="text-sm font-medium">Category<select className="field" name="category" value={filters.category} onChange={updateFilter}><option value="">All categories</option>{categories.map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></label>
        <label className="text-sm font-medium">Priority<select className="field" name="priority" value={filters.priority} onChange={updateFilter}><option value="">All priorities</option>{['urgent', 'high', 'medium', 'low'].map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="text-sm font-medium">Reply required<select className="field" name="reply_required" value={filters.reply_required} onChange={updateFilter}><option value="">Either</option><option value="true">Yes</option><option value="false">No</option></select></label>
      </section>
      {error && <ErrorState message={error} />}
      {!error && !emails && <LoadingState message="Loading persisted inbox…" />}
      {emails?.length === 0 && <NoData>No persisted emails match these filters. Sync Gmail to add messages.</NoData>}
      {emails?.length > 0 && <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{emails.map((email) => <PersistedEmailCard key={email.id} email={email} onView={viewDetails} />)}</div>}
      {selected && <PersistedEmailDetails email={selected} onClose={() => {
        setSelected(null)
        if (requestedEmailId) setSearchParams({}, { replace: true })
      }} />}
    </div>
  )
}
