import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import PWAInstallButton from './PWAInstallButton.jsx'
import ThemeToggle from './ThemeToggle.jsx'

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
    <header className="app-header sticky top-0 z-40 border-b backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-4 sm:px-8 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-3">
          <div aria-hidden="true" className="brand-mark">
            <img className="brand-mark__image brand-mark__image--light" src="/brand/inbox-copilot-light.jpg" />
            <img className="brand-mark__image brand-mark__image--dark" src="/brand/inbox-copilot-dark.png" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">AI Inbox Copilot</h1>
            <p className="text-sm text-slate-500">Turn email into clear next steps.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3 xl:justify-end">
          {user ? (
          <nav className="app-nav flex max-w-full flex-nowrap overflow-x-auto rounded-xl border p-1" aria-label="Primary navigation">
            <NavLink className={tabClass} end to="/">Dashboard</NavLink>
            <NavLink className={tabClass} to="/inbox">Inbox</NavLink>
            <NavLink className={tabClass} to="/tasks">Tasks</NavLink>
            <NavLink className={tabClass} to="/meetings">Meetings</NavLink>
            <NavLink className={tabClass} to="/analyze">Analyze Email</NavLink>
            <NavLink className={tabClass} to="/gmail">Gmail Inbox</NavLink>
            <NavLink className={tabClass} to="/assistant">AI Assistant</NavLink>
          </nav>
        ) : (
          <nav className="app-nav flex rounded-xl border p-1" aria-label="Public navigation">
            <NavLink className={tabClass} end to="/">About</NavLink>
            <NavLink className={tabClass} to="/gmail">Connect Gmail</NavLink>
          </nav>
        )}
          <PWAInstallButton />
          <ThemeToggle />
          {user && <div className="user-menu flex items-center gap-2 text-sm"><span className="max-w-40 truncate text-slate-500">{user.email || user.display_name}</span><button className="sign-out-button rounded-lg border px-3 py-2 font-semibold text-slate-600 hover:bg-slate-50" type="button" onClick={() => signOut().catch(() => {})}>Sign out</button></div>}
        </div>
      </div>
    </header>
  )
}
