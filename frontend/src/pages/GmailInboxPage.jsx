import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import GmailEmailCard from '../components/GmailEmailCard.jsx'
import GmailEmailDetails from '../components/GmailEmailDetails.jsx'
import { getGmailAuthUrl, getGmailStatus, getJobStatus, getPersistedEmails, syncGmailInbox } from '../services/api.js'

function persistedToSyncItem(email) {
  const grouped = { people: [], organizations: [], dates: [], locations: [] }
  const keys = { person: 'people', organization: 'organizations', date: 'dates', location: 'locations' }
  email.entities.forEach((entity) => grouped[keys[entity.entity_type]]?.push(entity.entity_value))
  return {
    message_id: email.gmail_message_id,
    source: 'cached',
    gmail: {
      message_id: email.gmail_message_id,
      thread_id: email.gmail_thread_id,
      sender: email.sender,
      recipients: email.recipients,
      subject: email.subject,
      body: email.body_original,
      received_at: email.received_at,
      labels: email.labels,
    },
    analysis: {
      sender: email.sender,
      subject: email.subject,
      summary: email.summary,
      classification: email.classification,
      tasks: email.tasks,
      meeting: email.meeting,
      entities: grouped,
      reply_required: email.reply_required,
    },
  }
}

export default function GmailInboxPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [gmailStatus, setGmailStatus] = useState(null)
  const [limit, setLimit] = useState(10)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [selected, setSelected] = useState(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncJob, setSyncJob] = useState(null)
  const [error, setError] = useState('')

  const callbackStatus = searchParams.get('gmail')
  const callbackReason = searchParams.get('reason')

  useEffect(() => {
    let active = true
    getGmailStatus()
      .then((status) => active && setGmailStatus(status))
      .catch((requestError) => {
        if (active) {
          setGmailStatus({ connected: false, can_read: false, can_send: false })
          setError(requestError.message)
        }
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!syncJob?.job_id || !['queued', 'running'].includes(syncJob.status)) return undefined
    let active = true
    let timer
    const poll = async () => {
      try {
        const next = await getJobStatus(syncJob.job_id)
        if (!active) return
        setSyncJob(next)
        if (['completed', 'partial_success'].includes(next.status)) {
          const emails = await getPersistedEmails({ limit, offset: 0 })
          if (!active) return
          setSyncResult({
            count: next.result?.total || emails.length,
            analyzed_count: (next.result?.processed || 0) + (next.result?.cached || 0),
            failed_count: next.result?.failed || 0,
            emails: emails.map(persistedToSyncItem),
          })
          setIsSyncing(false)
          return
        }
        if (next.status === 'failed') {
          setError(next.error || 'Inbox sync failed. You can retry safely.')
          setIsSyncing(false)
          return
        }
        timer = window.setTimeout(poll, 1000)
      } catch (requestError) {
        if (active) {
          setError(requestError.message)
          setIsSyncing(false)
        }
      }
    }
    poll()
    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [syncJob?.job_id, limit])

  const connect = async () => {
    setIsConnecting(true)
    setError('')
    try {
      window.location.assign(await getGmailAuthUrl())
    } catch (requestError) {
      setError(requestError.message)
      setIsConnecting(false)
    }
  }

  const sync = async () => {
    setIsSyncing(true)
    setError('')
    setSyncJob({ status: 'submitting', progress: { total: limit, processed: 0, failed: 0 } })
    try {
      const queued = await syncGmailInbox({ limit, unread_only: unreadOnly })
      setSyncJob({ ...queued, progress: { total: limit, processed: 0, failed: 0 } })
    } catch (requestError) {
      setError(requestError.message)
      setIsSyncing(false)
      if (requestError.message.toLowerCase().includes('not connected')) {
        setGmailStatus({ connected: false, can_read: false, can_send: false })
      }
    }
  }

  const clearCallbackNotice = () => {
    setSearchParams({}, { replace: true })
  }

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <section className="card">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Gmail inbox</p>
            <h2 className="mt-1 text-2xl font-semibold">Analyze your recent email</h2>
            <div className="mt-3 flex items-center gap-2 text-sm">
              <span className={`h-2.5 w-2.5 rounded-full ${gmailStatus?.connected ? 'bg-emerald-500' : gmailStatus?.connected === false ? 'bg-slate-300' : 'animate-pulse bg-amber-400'}`} />
              <span className="text-slate-600">
                {gmailStatus?.connected
                  ? `Gmail connected — ${gmailStatus.can_send ? 'read + send' : 'read-only'}`
                  : gmailStatus?.connected === false ? 'Gmail not connected' : 'Checking connection…'}
              </span>
            </div>
          </div>
          {gmailStatus?.connected === false && (
            <button className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-indigo-400" type="button" onClick={connect} disabled={isConnecting}>
              {isConnecting ? 'Opening Google…' : 'Connect Gmail'}
            </button>
          )}
        </div>

        {gmailStatus?.connected && (
          <div className="mt-6 flex flex-col gap-4 border-t pt-5 sm:flex-row sm:items-end">
            <label className="text-sm font-medium text-slate-700">
              Messages to analyze
              <select className="field block min-w-32" value={limit} onChange={(event) => setLimit(Number(event.target.value))} disabled={isSyncing}>
                <option value={5}>5 messages</option>
                <option value={10}>10 messages</option>
                <option value={20}>20 messages</option>
              </select>
            </label>
            <label className="flex items-center gap-2.5 pb-3 text-sm font-medium text-slate-700">
              <input className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} disabled={isSyncing} />
              Unread only
            </label>
            <button className="sm:ml-auto rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-indigo-400" type="button" onClick={sync} disabled={isSyncing}>
              {isSyncing ? `Syncing and analyzing ${limit} emails…` : 'Sync Inbox'}
            </button>
          </div>
        )}
      </section>

      {callbackStatus && (
        <div className={`mt-5 flex items-start justify-between gap-4 rounded-xl border p-4 text-sm ${callbackStatus === 'connected' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'}`} role="status">
          <span>{callbackStatus === 'connected' ? 'Gmail connected successfully.' : callbackReason || 'Gmail connection failed.'}</span>
          <button className="font-bold" type="button" onClick={clearCallbackNotice} aria-label="Dismiss">×</button>
        </div>
      )}

      {error && <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">{error}</div>}

      {isSyncing && (
        <div className="card mt-6 flex min-h-48 items-center justify-center text-center" aria-live="polite">
          <div><span className="mx-auto block h-8 w-8 animate-spin rounded-full border-4 border-indigo-100 border-t-indigo-600" /><p className="mt-4 font-semibold">Syncing inbox in the background…</p><p className="mt-2 text-lg font-bold text-indigo-700">{syncJob?.progress?.processed || 0} / {syncJob?.progress?.total || limit} emails processed</p><p className="mt-1 text-sm text-slate-500">You can navigate elsewhere; the worker will continue safely.</p>{syncJob?.reused && <p className="mt-2 text-xs text-amber-700">An existing sync job is already running, so it was reused.</p>}</div>
        </div>
      )}

      {!isSyncing && syncJob?.status === 'partial_success' && (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">
          Sync completed with partial success: {syncJob.result?.processed || 0} processed, {syncJob.result?.cached || 0} cached, and {syncJob.result?.failed || 0} failed. Retry Sync is safe.
        </div>
      )}

      {!isSyncing && syncResult && (
        <section className="mt-7">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div><h2 className="text-xl font-semibold">Inbox analysis</h2><p className="mt-1 text-sm text-slate-500">{syncResult.emails.filter((item) => item.source === 'processed').length} processed · {syncResult.emails.filter((item) => item.source === 'cached').length} cached · {syncResult.failed_count} failed · {syncResult.count} fetched</p></div>
          </div>
          {syncResult.emails.length ? (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {syncResult.emails.map((item) => <GmailEmailCard key={item.message_id} item={item} onView={setSelected} />)}
            </div>
          ) : (
            <div className="card text-center text-sm text-slate-500">No matching inbox messages were found.</div>
          )}
        </section>
      )}

      {selected && <GmailEmailDetails item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
