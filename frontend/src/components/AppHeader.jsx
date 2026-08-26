import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'

const tabClass = ({ isActive }) =>
  `rounded-lg px-3 py-2 text-sm font-semibold transition ${
    isActive
      ? 'bg-indigo-50 text-indigo-700'
      : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
  }`

export default function AppHeader() {
  const { session, signOut } = useAuth()
  const user = session?.user
  return (
    <header className="border-b bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-600 font-bold text-white">AI</div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">AI Inbox Copilot</h1>
            <p className="text-sm text-slate-500">Turn email into clear next steps.</p>
          </div>
        </div>
        <nav className="flex flex-wrap rounded-xl border bg-white p-1" aria-label="Primary navigation">
          <NavLink className={tabClass} end to="/">Dashboard</NavLink>
          <NavLink className={tabClass} to="/inbox">Inbox</NavLink>
          <NavLink className={tabClass} to="/tasks">Tasks</NavLink>
          <NavLink className={tabClass} to="/meetings">Meetings</NavLink>
          <NavLink className={tabClass} to="/analyze">Analyze Email</NavLink>
          <NavLink className={tabClass} to="/gmail">Gmail Inbox</NavLink>
          <NavLink className={tabClass} to="/assistant">AI Assistant</NavLink>
        </nav>
        {user && <div className="flex items-center gap-2 text-sm"><span className="max-w-40 truncate text-slate-500">{user.email || user.display_name}</span><button className="rounded-lg border px-3 py-2 font-semibold text-slate-600 hover:bg-slate-50" type="button" onClick={() => signOut().catch(() => {})}>Sign out</button></div>}
      </div>
    </header>
  )
}
