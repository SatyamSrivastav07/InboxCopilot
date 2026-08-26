import { useState } from 'react'

const INITIAL_EMAIL = { sender: '', subject: '', body: '' }

export default function EmailForm({ isLoading, onAnalyze }) {
  const [email, setEmail] = useState(INITIAL_EMAIL)

  const updateField = (event) => {
    const { name, value } = event.target
    setEmail((current) => ({ ...current, [name]: value }))
  }

  const submit = (event) => {
    event.preventDefault()
    onAnalyze({
      sender: email.sender.trim(),
      subject: email.subject.trim(),
      body: email.body.trim(),
    })
  }

  return (
    <form className="card" onSubmit={submit}>
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
          Email input
        </p>
        <h2 className="mt-1 text-xl font-semibold">Paste an email to analyze</h2>
      </div>

      <label className="block text-sm font-medium text-slate-700">
        Sender
        <input
          className="field"
          name="sender"
          type="text"
          autoComplete="email"
          placeholder="hr@example.com"
          value={email.sender}
          onChange={updateField}
          disabled={isLoading}
          required
        />
      </label>

      <label className="mt-5 block text-sm font-medium text-slate-700">
        Subject
        <input
          className="field"
          name="subject"
          type="text"
          placeholder="Joining Documents"
          value={email.subject}
          onChange={updateField}
          disabled={isLoading}
          required
        />
      </label>

      <label className="mt-5 block text-sm font-medium text-slate-700">
        Email body
        <textarea
          className="field min-h-56 resize-y leading-6"
          name="body"
          placeholder="Paste the email content here..."
          value={email.body}
          onChange={updateField}
          disabled={isLoading}
          required
        />
      </label>

      <button
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:bg-indigo-400"
        type="submit"
        disabled={isLoading}
      >
        {isLoading && (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
        )}
        {isLoading ? 'Analyzing email…' : 'Analyze Email'}
      </button>
    </form>
  )
}

