import { Link } from 'react-router-dom'

export default function AppFooter() {
  return (
    <footer className="app-footer border-t">
      <div className="mx-auto grid max-w-6xl gap-6 px-5 py-8 text-sm text-slate-500 sm:px-8 md:grid-cols-[1.5fr_1fr_1fr]">
        <div>
          <p className="font-semibold text-slate-800">AI Inbox Copilot</p>
          <p className="mt-2 max-w-sm leading-6">Turn email into clear next steps. Gmail access is always user-authorized.</p>
          <p className="mt-3 text-xs">© {new Date().getFullYear()} Satyam Srivastav.</p>
        </div>
        <nav className="flex flex-col gap-2" aria-label="Creator links">
          <p className="font-semibold text-slate-800">Connect</p>
          <a className="hover:text-indigo-700" href="mailto:satyamsricode07@gmail.com">Email Satyam</a>
          <a className="hover:text-indigo-700" href="https://www.linkedin.com/in/satyam-srivastav07/" target="_blank" rel="noreferrer">LinkedIn</a>
          <a className="hover:text-indigo-700" href="https://portfolio-blond-phi-6yszdranfc.vercel.app/" target="_blank" rel="noreferrer">Portfolio</a>
          <a className="hover:text-indigo-700" href="/resume/Satyam-Srivastav-Resume.pdf" target="_blank" rel="noreferrer">View resume</a>
        </nav>
        <nav className="flex flex-col gap-2" aria-label="Legal navigation">
          <p className="font-semibold text-slate-800">Legal</p>
          <Link className="hover:text-indigo-700" to="/privacy">Privacy</Link>
          <Link className="hover:text-indigo-700" to="/terms">Terms</Link>
          <Link className="hover:text-indigo-700" to="/data-deletion">Data deletion</Link>
        </nav>
      </div>
    </footer>
  )
}
