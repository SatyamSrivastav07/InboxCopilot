const labelize = (value) => value.replaceAll('_', ' ')

function Badge({ children, tone = 'slate' }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700',
    indigo: 'bg-indigo-50 text-indigo-700',
    amber: 'bg-amber-50 text-amber-800',
    rose: 'bg-rose-50 text-rose-700',
    emerald: 'bg-emerald-50 text-emerald-700',
  }
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>
}

function EntityGroup({ label, values }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.length ? values.map((value) => <Badge key={value}>{value}</Badge>) : <span className="text-sm text-slate-400">None</span>}
      </div>
    </div>
  )
}

export default function AnalysisResult({ analysis }) {
  const priorityTone = { urgent: 'rose', high: 'amber', medium: 'indigo', low: 'slate' }[analysis.classification.priority]

  return (
    <div className="space-y-4" aria-live="polite">
      <section className="card">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="indigo">{labelize(analysis.classification.category)}</Badge>
          <Badge tone={priorityTone}>{analysis.classification.priority} priority</Badge>
          <Badge tone={analysis.reply_required ? 'rose' : 'emerald'}>
            {analysis.reply_required ? 'Reply required' : 'No reply required'}
          </Badge>
        </div>
        <h2 className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Summary</h2>
        <p className="mt-2 leading-7 text-slate-700">{analysis.summary}</p>
        <p className="mt-4 border-t pt-4 text-sm leading-6 text-slate-500">{analysis.classification.reason}</p>
      </section>

      <section className="card">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Tasks & deadlines</h2>
          <Badge>{analysis.tasks.length}</Badge>
        </div>
        {analysis.tasks.length ? (
          <div className="mt-4 divide-y">
            {analysis.tasks.map((task, index) => (
              <div className="py-4 first:pt-0 last:pb-0" key={`${task.title}-${index}`}>
                <h3 className="font-medium text-slate-900">{task.title}</h3>
                {task.description && <p className="mt-1 text-sm leading-6 text-slate-500">{task.description}</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  {task.raw_deadline && <Badge tone="amber">Deadline: {task.raw_deadline}</Badge>}
                  {task.normalized_deadline && <Badge tone="indigo">{task.normalized_deadline}</Badge>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No actionable tasks found.</p>
        )}
      </section>

      <section className="card">
        <h2 className="text-lg font-semibold">Meeting</h2>
        {analysis.meeting ? (
          <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div><span className="text-slate-400">Title</span><p className="mt-1 font-medium">{analysis.meeting.title}</p></div>
            <div><span className="text-slate-400">Date & time</span><p className="mt-1 font-medium">{[analysis.meeting.date, analysis.meeting.time].filter(Boolean).join(' · ') || 'Not specified'}</p></div>
            <div><span className="text-slate-400">Participants</span><p className="mt-1 font-medium">{analysis.meeting.participants.join(', ') || 'Not specified'}</p></div>
            <div><span className="text-slate-400">Location or link</span><p className="mt-1 break-all font-medium">{analysis.meeting.location_or_link || 'Not specified'}</p></div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500">No meeting information found.</p>
        )}
      </section>

      <section className="card">
        <h2 className="text-lg font-semibold">Entities</h2>
        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          <EntityGroup label="People" values={analysis.entities.people} />
          <EntityGroup label="Organizations" values={analysis.entities.organizations} />
          <EntityGroup label="Dates" values={analysis.entities.dates} />
          <EntityGroup label="Locations" values={analysis.entities.locations} />
        </div>
      </section>
    </div>
  )
}

