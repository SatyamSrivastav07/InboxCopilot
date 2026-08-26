import { Link } from 'react-router-dom'

function LegalPage({ title, children }) {
  return <article className="mx-auto max-w-3xl px-5 py-12 sm:px-8"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">AI Inbox Copilot</p><h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">{title}</h2><p className="mt-3 text-sm text-slate-500">Last updated: 26 August 2026</p><div className="mt-8 space-y-7 leading-7 text-slate-700">{children}</div></article>
}

export function LegalSection({ title, children }) {
  return <section><h3 className="text-lg font-semibold text-slate-950">{title}</h3><div className="mt-2 space-y-3">{children}</div></section>
}

export default function PrivacyPage() {
  return <LegalPage title="Privacy Policy">
    <LegalSection title="What this service does"><p>AI Inbox Copilot helps you analyze Gmail messages you choose to sync, organize extracted tasks and meetings, search your inbox, and prepare reply drafts. It is an independent application and is not affiliated with Google.</p></LegalSection>
    <LegalSection title="Google data we access"><p>After you authorize Google access, the service requests Gmail read access to fetch messages for the features you use and Gmail send access only to send a reply that you explicitly approve. It also receives basic Google profile information needed to identify your account. It does not request permission to delete email, change labels, or manage your mailbox.</p></LegalSection>
    <LegalSection title="How data is used and stored"><p>Selected synced message content, metadata, and AI-generated results may be stored in your personal workspace so the inbox, task, meeting, search, and reply features work. OAuth credentials are encrypted before storage. Email content may be sent to the configured AI provider solely to generate the requested analysis or draft. We do not sell Google user data or use it for advertising.</p></LegalSection>
    <LegalSection title="Sharing and retention"><p>Data is processed by the infrastructure and AI providers needed to operate the service, including hosting, database, queue, and AI-processing providers. Data is not shared for unrelated purposes. We retain workspace data while your account is active or until deletion is requested, subject to necessary security, legal, and operational retention.</p></LegalSection>
    <LegalSection title="Your choices"><p>You can stop new Gmail access by revoking this app in your Google Account security settings. To request deletion of your stored account and workspace data, follow the <Link className="font-medium text-indigo-700 hover:underline" to="/data-deletion">data deletion instructions</Link>.</p></LegalSection>
    <LegalSection title="Contact"><p>For privacy questions or a deletion request, email <a className="font-medium text-indigo-700 hover:underline" href="mailto:satyamsricode07@gmail.com">satyamsricode07@gmail.com</a>.</p></LegalSection>
  </LegalPage>
}
