const labelize = (value) => value.replaceAll('_', ' ')

const priorityStyles = {
  urgent: 'bg-rose-50 text-rose-700',
  high: 'bg-amber-50 text-amber-800',
  medium: 'bg-indigo-50 text-indigo-700',
  low: 'bg-slate-100 text-slate-700',
}

function formatDate(value) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export default function GmailEmailCard({ item, onView }) {
  if (!item.analysis || !item.gmail) {
    return (
      <article className="card border-rose-200">
        <p className="text-sm font-semibold text-rose-700">Could not analyze message</p>
        <p className="mt-2 text-sm text-slate-500">{item.error || 'Analysis failed.'}</p>
        <p className="mt-3 break-all text-xs text-slate-400">Message ID: {item.message_id}</p>
      </article>
    )
  }

  const { gmail, analysis } = item
  return (
    <article className="card flex h-full flex-col">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-500">{gmail.sender || 'Unknown sender'}</p>
          <h2 className="mt-1 line-clamp-2 text-lg font-semibold text-slate-900">{gmail.subject}</h2>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          {item.source && <span className={`rounded-full px-2 py-1 text-[11px] font-bold uppercase tracking-wide ${item.source === 'cached' ? 'bg-emerald-50 text-emerald-700' : 'bg-violet-50 text-violet-700'}`}>{item.source}</span>}
          {gmail.labels.includes('UNREAD') && <span className="rounded-full bg-blue-50 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-blue-700">Unread</span>}
        </div>
      </div>
      <p className="mt-2 text-xs text-slate-400">{formatDate(gmail.received_at)}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">{labelize(analysis.classification.category)}</span>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${priorityStyles[analysis.classification.priority]}`}>{analysis.classification.priority}</span>
      </div>
      <p className="mt-4 line-clamp-3 text-sm leading-6 text-slate-600">{analysis.summary}</p>
      <div className="mt-5 grid grid-cols-3 gap-2 border-t pt-4 text-center text-xs">
        <div><p className="font-bold text-slate-800">{analysis.reply_required ? 'Yes' : 'No'}</p><p className="mt-1 text-slate-400">Reply</p></div>
        <div><p className="font-bold text-slate-800">{analysis.tasks.length}</p><p className="mt-1 text-slate-400">Tasks</p></div>
        <div><p className="font-bold text-slate-800">{analysis.meeting ? 'Yes' : 'No'}</p><p className="mt-1 text-slate-400">Meeting</p></div>
      </div>
      <button className="mt-5 rounded-xl border px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700" type="button" onClick={() => onView(item)}>
        View Details
      </button>
    </article>
  )
}
