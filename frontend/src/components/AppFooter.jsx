import { Link } from 'react-router-dom'

export default function AppFooter() {
  return (
    <footer className="app-footer border-t">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-6 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <p>© {new Date().getFullYear()} AI Inbox Copilot. Gmail access is always user-authorized.</p>
        <nav className="flex flex-wrap gap-x-4 gap-y-2" aria-label="Legal navigation">
          <Link className="hover:text-indigo-700" to="/privacy">Privacy</Link>
          <Link className="hover:text-indigo-700" to="/terms">Terms</Link>
          <Link className="hover:text-indigo-700" to="/data-deletion">Data deletion</Link>
        </nav>
      </div>
    </footer>
  )
}
