import { Link } from 'react-router-dom'
import { LegalSection } from './PrivacyPage.jsx'

export default function TermsPage() {
  return <article className="mx-auto max-w-3xl px-5 py-12 sm:px-8"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">AI Inbox Copilot</p><h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Terms of Service</h2><p className="mt-3 text-sm text-slate-500">Last updated: 26 August 2026</p><div className="mt-8 space-y-7 leading-7 text-slate-700">
    <LegalSection title="Using the service"><p>You may use AI Inbox Copilot only with a Google account you are authorized to access. You are responsible for the information you sync and for complying with applicable laws, workplace rules, and your email provider’s terms.</p></LegalSection>
    <LegalSection title="AI output and sending"><p>Summaries, classifications, extracted tasks, and reply drafts may be inaccurate or incomplete. Review output before acting on it. A reply is sent only after you explicitly approve it; you remain responsible for every message sent from your account.</p></LegalSection>
    <LegalSection title="Availability and changes"><p>The service may change, be unavailable, or be discontinued. Gmail and AI provider quotas can also affect availability. Do not rely on the service as the sole source for critical deadlines, legal notices, or emergency communication.</p></LegalSection>
    <LegalSection title="Privacy"><p>Your use of Gmail data is described in the <Link className="font-medium text-indigo-700 hover:underline" to="/privacy">Privacy Policy</Link>. By connecting Gmail, you authorize the limited access shown in Google’s consent screen.</p></LegalSection>
    <LegalSection title="Contact"><p>Questions about these terms can be sent to <a className="font-medium text-indigo-700 hover:underline" href="mailto:satyamsricode07@gmail.com">satyamsricode07@gmail.com</a>.</p></LegalSection>
  </div></article>
}
