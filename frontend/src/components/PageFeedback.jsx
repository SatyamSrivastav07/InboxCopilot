export function LoadingState({ message = 'Loading…' }) {
  return (
    <div className="card flex min-h-48 items-center justify-center text-center" aria-live="polite">
      <div>
        <span className="mx-auto block h-8 w-8 animate-spin rounded-full border-4 border-indigo-100 border-t-indigo-600" />
        <p className="mt-4 text-sm font-semibold text-slate-600">{message}</p>
      </div>
    </div>
  )
}

export function ErrorState({ message }) {
  return <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">{message}</div>
}

export function NoData({ children }) {
  return <div className="card py-12 text-center text-sm text-slate-500">{children}</div>
}

