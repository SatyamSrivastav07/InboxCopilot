import AnalysisResult from './AnalysisResult.jsx'

function formatDate(value) {
  if (!value) return 'Not available'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

export default function GmailEmailDetails({ item, onClose }) {
  if (!item?.gmail || !item.analysis) return null
  const { gmail, analysis } = item

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-4 sm:p-8" role="dialog" aria-modal="true" aria-labelledby="gmail-detail-title">
      <div className="mx-auto max-w-4xl rounded-2xl bg-canvas shadow-2xl">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 rounded-t-2xl border-b bg-white px-5 py-4 sm:px-7">
          <div className="min-w-0">
            <p className="text-sm text-slate-500">Email details</p>
            <h2 className="truncate text-lg font-semibold" id="gmail-detail-title">{gmail.subject}</h2>
          </div>
          <button className="rounded-lg border px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50" type="button" onClick={onClose}>Close</button>
        </div>
        <div className="space-y-4 p-5 sm:p-7">
          <section className="card">
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-400">Sender</dt><dd className="mt-1 break-words font-medium">{gmail.sender || 'Unknown'}</dd></div>
              <div><dt className="text-slate-400">Recipients</dt><dd className="mt-1 break-words font-medium">{gmail.recipients.join(', ') || 'Not listed'}</dd></div>
              <div><dt className="text-slate-400">Received</dt><dd className="mt-1 font-medium">{formatDate(gmail.received_at)}</dd></div>
              <div><dt className="text-slate-400">Labels</dt><dd className="mt-1 font-medium">{gmail.labels.join(', ') || 'None'}</dd></div>
            </dl>
          </section>
          <section className="card">
            <h3 className="text-lg font-semibold">Original email</h3>
            <pre className="mt-4 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-50 p-4 font-sans text-sm leading-6 text-slate-700">{gmail.body || '(Empty body)'}</pre>
          </section>
          <AnalysisResult analysis={analysis} />
        </div>
      </div>
    </div>
  )
}

