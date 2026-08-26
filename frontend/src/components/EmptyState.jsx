export default function EmptyState() {
  return (
    <div className="card flex min-h-72 flex-col items-center justify-center text-center">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-indigo-50 text-2xl" aria-hidden="true">
        ✦
      </div>
      <h2 className="mt-4 text-lg font-semibold">Your analysis will appear here</h2>
      <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
        Add the sender, subject, and email body to identify priority, tasks, meetings, and key entities.
      </p>
    </div>
  )
}

