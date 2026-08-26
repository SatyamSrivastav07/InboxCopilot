import { useEffect, useState } from 'react'

import { ErrorState, LoadingState, NoData } from '../components/PageFeedback.jsx'
import { getMeetings } from '../services/api.js'

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { getMeetings().then(setMeetings).catch((requestError) => setError(requestError.message)) }, [])

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <div className="mb-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Schedule</p><h2 className="mt-1 text-3xl font-semibold">Meetings</h2><p className="mt-2 text-sm text-slate-500">Meeting information extracted from persisted email.</p></div>
      {error && <ErrorState message={error} />}
      {!error && !meetings && <LoadingState message="Loading meetings…" />}
      {meetings?.length === 0 && <NoData>No meetings have been extracted yet.</NoData>}
      {meetings?.length > 0 && <div className="grid gap-5 md:grid-cols-2">{meetings.map((meeting) => (
        <article className="card" key={meeting.id}>
          <div className="flex items-start justify-between gap-3"><h3 className="text-lg font-semibold">{meeting.title}</h3><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">Meeting</span></div>
          <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2"><div><dt className="text-slate-400">Date</dt><dd className="mt-1 font-medium">{meeting.normalized_date || meeting.raw_date || 'Not specified'}</dd></div><div><dt className="text-slate-400">Time</dt><dd className="mt-1 font-medium">{meeting.time || 'Not specified'}</dd></div><div><dt className="text-slate-400">Participants</dt><dd className="mt-1 font-medium">{meeting.participants.join(', ') || 'Not specified'}</dd></div><div><dt className="text-slate-400">Location / link</dt><dd className="mt-1 break-all font-medium">{meeting.location_or_link || 'Not specified'}</dd></div></dl>
          <p className="mt-5 border-t pt-4 text-xs text-slate-400">Source: {meeting.source_email?.subject || 'Unknown email'}</p>
        </article>
      ))}</div>}
    </div>
  )
}
