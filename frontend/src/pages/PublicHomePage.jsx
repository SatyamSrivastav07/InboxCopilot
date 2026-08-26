import { Link } from 'react-router-dom'

const features = [
  ['Understand email', 'Generate concise summaries, categories, priority signals, tasks, meetings, and entities from messages you choose to sync.'],
  ['Find what matters', 'Use structured inbox views and source-backed search to find action items and important context faster.'],
  ['Keep replies human-controlled', 'Create an editable draft, then review and explicitly approve it before any email is sent.'],
]

export default function PublicHomePage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-20">
      <section className="public-hero grid gap-10 rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-sky-50 p-8 shadow-sm md:grid-cols-[1.35fr_0.65fr] md:p-12">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">Your Gmail, made actionable</p>
          <h2 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl">Turn email into clear next steps.</h2>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">AI Inbox Copilot connects only after you authorize it with Google. It helps you analyze selected Gmail messages, organize their information, search your inbox, and prepare reply drafts for your review.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700" to="/gmail">Connect Gmail securely</Link>
            <Link className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50" to="/privacy">How your data is used</Link>
          </div>
        </div>
        <aside className="public-permissions rounded-2xl border border-indigo-100 bg-white/90 p-6 text-sm shadow-sm">
          <p className="font-semibold text-slate-900">Gmail permissions</p>
          <ul className="mt-4 space-y-3 leading-6 text-slate-600">
            <li><span className="font-medium text-slate-800">Read:</span> access selected email content to provide analysis and search.</li>
            <li><span className="font-medium text-slate-800">Send:</span> send only a reply you explicitly approve.</li>
            <li><span className="font-medium text-slate-800">Control:</span> disconnect access in your Google Account at any time.</li>
          </ul>
        </aside>
      </section>

      <section className="mt-14">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Built for intentional email work</p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">You stay in control at every step.</h2>
        <div className="mt-7 grid gap-5 md:grid-cols-3">
          {features.map(([title, description]) => (
            <article className="rounded-2xl border bg-white p-6 shadow-sm" key={title}>
              <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
              <p className="mt-3 leading-7 text-slate-600">{description}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
