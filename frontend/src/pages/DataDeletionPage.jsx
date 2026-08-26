import { LegalSection } from './PrivacyPage.jsx'

export default function DataDeletionPage() {
  return <article className="mx-auto max-w-3xl px-5 py-12 sm:px-8"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">AI Inbox Copilot</p><h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Data deletion</h2><p className="mt-3 text-sm text-slate-500">How to remove Gmail access and request workspace deletion</p><div className="mt-8 space-y-7 leading-7 text-slate-700">
    <LegalSection title="1. Revoke Gmail access"><p>In your Google Account, open Security, then Third-party apps and services. Find AI Inbox Copilot and remove its access. This prevents future Gmail API access.</p></LegalSection>
    <LegalSection title="2. Request deletion from this service"><p>Email <a className="font-medium text-indigo-700 hover:underline" href="mailto:satyamsricode07@gmail.com?subject=AI%20Inbox%20Copilot%20data%20deletion%20request">satyamsricode07@gmail.com</a> from the Google account connected to AI Inbox Copilot. Use the subject “AI Inbox Copilot data deletion request”.</p></LegalSection>
    <LegalSection title="What is deleted"><p>After identity verification, the request covers the stored account profile, encrypted Gmail credentials, synced email records, extracted tasks/meetings/entities, reply drafts, and associated search index data for that account, subject to limited security or legal retention.</p></LegalSection>
  </div></article>
}
