import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { askInbox, semanticSearch } from '../services/api.js'

const examples = [
  'What deadlines are mentioned in my recent emails?',
  'Which emails need my reply?',
  'Summarize the important updates in my inbox.',
]

function Sources({ sources, onOpen }) {
  if (!sources?.length) return null
  return (
    <div className="mt-5 border-t pt-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Sources</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {sources.map((source) => (
          <button
            className="rounded-xl border bg-slate-50 p-3 text-left transition hover:border-indigo-300 hover:bg-indigo-50"
            key={source.email_id}
            onClick={() => onOpen(source.email_id)}
            type="button"
          >
            <span className="block text-sm font-semibold text-slate-900">{source.subject}</span>
            <span className="mt-1 block text-xs text-slate-500">{source.sender}</span>
            <span className="mt-2 block text-xs leading-5 text-slate-600">{source.snippet}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export default function AssistantPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('ask')
  const [query, setQuery] = useState('')
  const [history, setHistory] = useState([])
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const openEmail = (emailId) => navigate(`/inbox?email=${emailId}`)

  const submit = async (event) => {
    event.preventDefault()
    const value = query.trim()
    if (!value || loading) return
    setLoading(true)
    setError('')
    try {
      if (mode === 'ask') {
        const response = await askInbox(value)
        setHistory((items) => [...items, { question: value, ...response }])
      } else {
        const response = await semanticSearch(value)
        setResults(response.results)
      }
      setQuery('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Grounded inbox intelligence</p>
        <h2 className="mt-1 text-3xl font-semibold">Ask Your Inbox</h2>
        <p className="mt-2 text-sm text-slate-500">Ask questions or find messages by meaning. Answers use only indexed email evidence.</p>
      </div>

      <div className="mb-5 inline-flex rounded-xl border bg-white p-1">
        {['ask', 'search'].map((item) => (
          <button
            className={`rounded-lg px-4 py-2 text-sm font-semibold ${mode === item ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500'}`}
            key={item}
            onClick={() => { setMode(item); setError('') }}
            type="button"
          >
            {item === 'ask' ? 'Ask Inbox' : 'Semantic Search'}
          </button>
        ))}
      </div>

      {mode === 'ask' && history.length === 0 && (
        <section className="card mb-5">
          <p className="text-sm font-semibold">Try asking</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {examples.map((example) => <button className="rounded-full bg-slate-100 px-3 py-2 text-left text-xs text-slate-600 hover:bg-indigo-50 hover:text-indigo-700" key={example} onClick={() => setQuery(example)} type="button">{example}</button>)}
          </div>
        </section>
      )}

      {mode === 'ask' && history.map((item, index) => (
        <section className="card mb-5" key={`${item.question}-${index}`}>
          <p className="text-sm font-semibold text-indigo-700">You</p>
          <p className="mt-1 text-sm text-slate-700">{item.question}</p>
          <p className="mt-5 text-sm font-semibold text-emerald-700">Inbox Copilot</p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-800">{item.answer}</p>
          <Sources sources={item.sources} onOpen={openEmail} />
        </section>
      ))}

      {mode === 'search' && results.length > 0 && (
        <section className="card mb-5">
          <p className="text-sm font-semibold">Closest matching emails</p>
          <Sources sources={results} onOpen={openEmail} />
        </section>
      )}

      {error && <div className="mb-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}

      <form className="card sticky bottom-4" onSubmit={submit}>
        <label className="text-sm font-semibold" htmlFor="assistant-query">{mode === 'ask' ? 'Ask about your inbox' : 'Search by meaning'}</label>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row">
          <input
            className="field mt-0"
            id="assistant-query"
            maxLength={mode === 'ask' ? 2000 : 1000}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={mode === 'ask' ? 'What should I follow up on this week?' : 'contract renewal discussed last month'}
            value={query}
          />
          <button className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60" disabled={!query.trim() || loading} type="submit">
            {loading ? 'Working…' : mode === 'ask' ? 'Ask' : 'Search'}
          </button>
        </div>
      </form>
    </div>
  )
}
