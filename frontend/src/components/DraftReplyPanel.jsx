import { useState } from 'react'

import {
  approveReplyDraft,
  generateReplyDraft,
  sendReplyDraft,
  updateReplyDraft,
} from '../services/api.js'

const tones = ['professional', 'concise', 'friendly', 'formal']

export default function DraftReplyPanel({ email, onClose, initialDraft = null }) {
  const [tone, setTone] = useState('professional')
  const [instruction, setInstruction] = useState('')
  const [draft, setDraft] = useState(initialDraft)
  const [body, setBody] = useState(initialDraft?.body || '')
  const [dirty, setDirty] = useState(false)
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')
  const [confirmSend, setConfirmSend] = useState(false)

  const generate = async () => {
    setLoading('Generating thread-aware draft…')
    setError('')
    try {
      const result = await generateReplyDraft(email.id, {
        instruction: instruction.trim() || null,
        tone,
      })
      setDraft(result)
      setBody(result.body)
      setDirty(false)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading('')
    }
  }

  const save = async () => {
    if (!draft || !body.trim()) return null
    setLoading('Saving changes…')
    setError('')
    try {
      const result = await updateReplyDraft(draft.draft_id, body)
      setDraft(result)
      setBody(result.body)
      setDirty(false)
      return result
    } catch (requestError) {
      setError(requestError.message)
      return null
    } finally {
      setLoading('')
    }
  }

  const approve = async () => {
    let current = draft
    if (dirty) current = await save()
    if (!current) return
    setLoading('Approving exact text…')
    setError('')
    try {
      const result = await approveReplyDraft(current.draft_id)
      setDraft(result)
      setBody(result.body)
      setDirty(false)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading('')
    }
  }

  const send = async () => {
    setLoading('Sending approved reply…')
    setError('')
    try {
      const result = await sendReplyDraft(draft.draft_id)
      setDraft((current) => ({ ...current, ...result }))
      setConfirmSend(false)
    } catch (requestError) {
      setError(requestError.message)
      setDraft((current) => current ? { ...current, status: 'failed' } : current)
      setConfirmSend(false)
    } finally {
      setLoading('')
    }
  }

  const editBody = (event) => {
    setBody(event.target.value)
    setDirty(true)
    setDraft((current) => current ? { ...current, status: 'draft' } : current)
  }

  return (
    <div className="fixed inset-0 z-[60] overflow-y-auto bg-slate-950/60 p-4 sm:p-8" role="dialog" aria-modal="true" aria-labelledby="draft-reply-title">
      <div className="mx-auto max-w-3xl rounded-2xl bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b px-5 py-4 sm:px-7">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">Human approval required</p>
            <h2 className="mt-1 text-xl font-semibold" id="draft-reply-title">Draft Reply</h2>
          </div>
          <button className="rounded-lg border px-3 py-2 text-sm font-semibold text-slate-600" onClick={onClose} type="button">Close</button>
        </header>

        <div className="space-y-5 p-5 sm:p-7">
          <section className="rounded-xl bg-slate-50 p-4 text-sm">
            <p><span className="text-slate-500">Source sender:</span> <span className="font-medium">{draft?.recipient || email.sender}</span></p>
            <p className="mt-1"><span className="text-slate-500">Subject:</span> <span className="font-medium">{draft?.subject || `Re: ${email.subject.replace(/^(re:\s*)+/i, '')}`}</span></p>
            {draft?.thread_message_count && <p className="mt-1 text-slate-500">Context uses {draft.thread_message_count} Gmail thread messages.</p>}
          </section>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium">Tone<select className="field" value={tone} onChange={(event) => setTone(event.target.value)} disabled={draft?.status === 'sent'}>{tones.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label className="text-sm font-medium">Optional instruction<input className="field" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Ask whether Friday afternoon works." disabled={draft?.status === 'sent'} /></label>
          </div>

          {!draft && <button className="w-full rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white disabled:opacity-60" disabled={Boolean(loading)} onClick={generate} type="button">Generate Draft</button>}

          {draft && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={`rounded-full px-2.5 py-1 font-semibold uppercase ${draft.status === 'sent' ? 'bg-emerald-50 text-emerald-700' : draft.status === 'approved' ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'}`}>{draft.status}</span>
                <span className="text-slate-500">Generated text and your edited text are stored separately.</span>
              </div>
              {(draft.attachment_warning || draft.notes?.length > 0) && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{draft.attachment_warning && <p className="font-semibold">Attachment sending is not supported.</p>}{draft.notes?.map((note) => <p className="mt-1" key={note}>{note}</p>)}</div>}
              <label className="block text-sm font-medium">Reply body<textarea className="field min-h-64 resize-y leading-6" value={body} onChange={editBody} disabled={draft.status === 'sent'} /></label>
              <div className="flex flex-wrap gap-3">
                <button className="rounded-xl border px-4 py-2.5 text-sm font-semibold disabled:opacity-50" onClick={generate} disabled={Boolean(loading) || draft.status === 'sent'} type="button">Regenerate</button>
                <button className="rounded-xl border px-4 py-2.5 text-sm font-semibold disabled:opacity-50" onClick={save} disabled={Boolean(loading) || !dirty || !body.trim() || draft.status === 'sent'} type="button">Save Changes</button>
                <button className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" onClick={approve} disabled={Boolean(loading) || !body.trim() || draft.status === 'approved' || draft.status === 'sent'} type="button">Approve Exact Text</button>
                <button className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" onClick={() => setConfirmSend(true)} disabled={Boolean(loading) || dirty || draft.status !== 'approved'} type="button">Send Reply</button>
              </div>
              {draft.status === 'sent' && <p className="rounded-xl bg-emerald-50 p-4 text-sm font-semibold text-emerald-700">Reply sent successfully. This draft cannot be sent again.</p>}
            </>
          )}

          {loading && <p className="text-sm text-indigo-600">{loading}</p>}
          {error && <p className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</p>}
        </div>
      </div>

      {confirmSend && (
        <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/60 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-semibold">Send this approved reply?</h3>
            <p className="mt-3 text-sm text-slate-600">To: <span className="font-semibold text-slate-900">{draft.recipient}</span></p>
            <p className="mt-1 text-sm text-slate-600">Subject: <span className="font-semibold text-slate-900">{draft.subject}</span></p>
            <p className="mt-3 text-sm text-rose-700">This action sends the exact approved text through Gmail.</p>
            <div className="mt-5 flex justify-end gap-3"><button className="rounded-xl border px-4 py-2.5 text-sm font-semibold" disabled={Boolean(loading)} onClick={() => setConfirmSend(false)} type="button">Cancel</button><button className="rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60" disabled={Boolean(loading)} onClick={send} type="button">{loading ? 'Sending…' : 'Send Reply'}</button></div>
          </div>
        </div>
      )}
    </div>
  )
}
