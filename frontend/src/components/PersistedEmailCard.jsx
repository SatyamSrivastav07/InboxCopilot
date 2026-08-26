const labelize = (value) => value.replaceAll('_', ' ')

function formatDate(value) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export default function PersistedEmailCard({ email, onView, onReprocess, reprocessing }) {
  return (
    <article className="card flex h-full flex-col">
      <p className="truncate text-sm font-medium text-slate-500">{email.sender || 'Unknown sender'}</p>
      <h2 className="mt-1 line-clamp-2 text-lg font-semibold">{email.subject}</h2>
      <p className="mt-2 text-xs text-slate-400">{formatDate(email.received_at)}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">{labelize(email.classification.category)}</span>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${['urgent', 'high'].includes(email.classification.priority) ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>{email.classification.priority}</span>
        {email.reply_required && <span className="rounded-full bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700">Reply required</span>}
      </div>
      <p className="mt-4 line-clamp-3 flex-1 text-sm leading-6 text-slate-600">{email.summary}</p>
      {email.processing_status === 'failed' && (
        <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
          <p>{email.processing_error || 'Analysis failed after retries.'}</p>
          <button className="mt-2 font-semibold underline disabled:opacity-50" type="button" disabled={reprocessing} onClick={() => onReprocess(email.id)}>
            {reprocessing ? 'Reprocessing…' : 'Retry analysis'}
          </button>
        </div>
      )}
      {email.vector_status === 'failed' && email.processing_status !== 'failed' && (
        <p className="mt-3 text-xs font-medium text-amber-700">Semantic indexing failed; reprocess to retry indexing.</p>
      )}
      <button className="mt-5 rounded-xl border px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700" type="button" onClick={() => onView(email.id)}>View Details</button>
    </article>
  )
}
