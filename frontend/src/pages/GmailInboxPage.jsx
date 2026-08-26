import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext.jsx'
import GmailEmailCard from '../components/GmailEmailCard.jsx'
import GmailEmailDetails from '../components/GmailEmailDetails.jsx'
import { deleteAccount, disconnectGmail, getGmailAuthUrl, getGmailStatus, getJobStatus, getPersistedEmails, syncGmailInbox } from '../services/api.js'

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
  const { session, loading: sessionLoading, refreshSession } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [gmailStatus, setGmailStatus] = useState(null)
  const [limit, setLimit] = useState(10)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [selected, setSelected] = useState(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncJob, setSyncJob] = useState(null)
  const [showDeleteAccount, setShowDeleteAccount] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [isRemovingData, setIsRemovingData] = useState(false)
  const [error, setError] = useState('')
  const automaticSyncStarted = useRef(false)

  const callbackStatus = searchParams.get('gmail')
  const callbackReason = searchParams.get('reason')

  useEffect(() => {
    if (!session?.authenticated) return undefined
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
  }, [session?.authenticated])

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

  useEffect(() => {
    if (callbackStatus === 'connected') refreshSession().catch(() => {})
  }, [callbackStatus])

  const sync = async ({ requestedLimit = limit, requestedUnreadOnly = unreadOnly } = {}) => {
    setIsSyncing(true)
    setError('')
    setSyncJob({ status: 'submitting', progress: { total: requestedLimit, processed: 0, failed: 0 } })
    try {
      const result = await syncGmailInbox({ limit: requestedLimit, unread_only: requestedUnreadOnly })
      if (['completed', 'partial_success', 'failed'].includes(result.status)) {
        setSyncJob(result)
        if (result.status === 'failed') {
          setError(result.error || 'Inbox sync failed. You can retry safely.')
        } else {
          const emails = await getPersistedEmails({ limit: requestedLimit, offset: 0 })
          setSyncResult({
            count: result.result?.total || emails.length,
            analyzed_count: (result.result?.processed || 0) + (result.result?.cached || 0),
            failed_count: result.result?.failed || 0,
            emails: emails.map(persistedToSyncItem),
          })
        }
        setIsSyncing(false)
        return
      }
      setSyncJob({ ...result, progress: { total: requestedLimit, processed: 0, failed: 0 } })
    } catch (requestError) {
      setError(requestError.message)
      setIsSyncing(false)
      if (requestError.message.toLowerCase().includes('not connected')) {
        setGmailStatus({ connected: false, can_read: false, can_send: false })
      }
    }
  }

  useEffect(() => {
    if (automaticSyncStarted.current || callbackStatus !== 'connected' || !session?.authenticated || !gmailStatus?.connected) return
    automaticSyncStarted.current = true
    void sync({ requestedLimit: 10, requestedUnreadOnly: false })
  }, [callbackStatus, gmailStatus?.connected, session?.authenticated])

  const clearCallbackNotice = () => {
    setSearchParams({}, { replace: true })
  }

  const disconnect = async () => {
    setIsRemovingData(true)
    setError('')
    try {
      await disconnectGmail()
      setGmailStatus({ connected: false, can_read: false, can_send: false })
      setSyncResult(null)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsRemovingData(false)
    }
  }

  const removeAccount = async () => {
    if (deleteConfirmation !== 'DELETE') return
    setIsRemovingData(true)
    setError('')
    try {
      await deleteAccount()
      await refreshSession()
    } catch (requestError) {
      setError(requestError.message)
      setIsRemovingData(false)
    }
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
                {!session?.authenticated
                  ? 'Sign in to securely connect your Gmail'
                  : gmailStatus?.connected
                  ? `Gmail connected — ${gmailStatus.can_send ? 'read + send' : 'read-only'}`
                  : gmailStatus?.connected === false ? 'Gmail not connected' : 'Checking connection…'}
              </span>
            </div>
          </div>
          {!sessionLoading && (!session?.authenticated || gmailStatus?.connected === false) && (
            <button className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-indigo-400" type="button" onClick={connect} disabled={isConnecting}>
              {isConnecting ? 'Opening Google…' : session?.authenticated ? 'Connect Gmail' : 'Sign in with Google'}
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
              {isSyncing ? `Syncing and analyzing ${syncJob?.progress?.total || limit} emails…` : 'Sync Inbox'}
            </button>
          </div>
        )}
      </section>

      {callbackStatus && (
        <div className={`mt-5 flex items-start justify-between gap-4 rounded-xl border p-4 text-sm ${callbackStatus === 'connected' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'}`} role="status">
          <span>{callbackStatus === 'connected' ? 'Gmail connected successfully. Your first 10 emails are syncing automatically.' : callbackReason || 'Gmail connection failed.'}</span>
          <button className="font-bold" type="button" onClick={clearCallbackNotice} aria-label="Dismiss">×</button>
        </div>
      )}

      {error && <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">{error}</div>}

      {isSyncing && (
        <div className="card mt-6 flex min-h-48 items-center justify-center text-center" aria-live="polite">
          <div><span className="mx-auto block h-8 w-8 animate-spin rounded-full border-4 border-indigo-100 border-t-indigo-600" /><p className="mt-4 font-semibold">Syncing and analyzing your inbox…</p><p className="mt-2 text-lg font-bold text-indigo-700">{syncJob?.progress?.processed || 0} / {syncJob?.progress?.total || limit} emails processed</p><p className="mt-1 text-sm text-slate-500">Keep this tab open until the sync completes.</p>{syncJob?.reused && <p className="mt-2 text-xs text-amber-700">An existing sync job is already running, so it was reused.</p>}</div>
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

      {session?.authenticated && (
        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900">Your data controls</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">Disconnecting removes this app’s saved Gmail credentials. Deleting your account permanently removes your stored inbox data, generated drafts, and search index from AI Inbox Copilot.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            {gmailStatus?.connected && <button className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50" type="button" onClick={disconnect} disabled={isRemovingData}>Disconnect Gmail</button>}
            <button className="rounded-xl border border-rose-300 px-4 py-2.5 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50" type="button" onClick={() => setShowDeleteAccount((visible) => !visible)} disabled={isRemovingData}>Delete account data</button>
          </div>
          {showDeleteAccount && <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-4"><p className="text-sm font-medium text-rose-900">This cannot be undone. Type <code className="rounded bg-white px-1.5 py-0.5">DELETE</code> to permanently remove your account data.</p><div className="mt-3 flex flex-col gap-3 sm:flex-row"><input className="field flex-1 bg-white" value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} placeholder="Type DELETE" aria-label="Account deletion confirmation" /><button className="rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:bg-rose-300" type="button" onClick={removeAccount} disabled={deleteConfirmation !== 'DELETE' || isRemovingData}>{isRemovingData ? 'Deleting…' : 'Permanently delete'}</button></div></div>}
        </section>
      )}

      {selected && <GmailEmailDetails item={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
