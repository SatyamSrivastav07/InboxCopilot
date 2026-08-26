import { useEffect, useState } from 'react'

import { ErrorState, LoadingState, NoData } from '../components/PageFeedback.jsx'
import { getTasks, updateTask } from '../services/api.js'

export default function TasksPage() {
  const [completedFilter, setCompletedFilter] = useState('false')
  const [tasks, setTasks] = useState(null)
  const [updating, setUpdating] = useState(null)
  const [error, setError] = useState('')

  const load = () => {
    setTasks(null)
    setError('')
    const filters = completedFilter === '' ? {} : { completed: completedFilter }
    getTasks(filters).then(setTasks).catch((requestError) => setError(requestError.message))
  }
  useEffect(load, [completedFilter])

  const toggle = async (task) => {
    setUpdating(task.id)
    setError('')
    try {
      const updated = await updateTask(task.id, !task.completed)
      if (completedFilter === '') setTasks((items) => items.map((item) => item.id === task.id ? updated : item))
      else setTasks((items) => items.filter((item) => item.id !== task.id))
    } catch (requestError) { setError(requestError.message) } finally { setUpdating(null) }
  }

  return (
    <div className="mx-auto max-w-4xl px-5 py-8 sm:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">Action center</p><h2 className="mt-1 text-3xl font-semibold">Tasks</h2></div><label className="text-sm font-medium">Status<select className="field min-w-40" value={completedFilter} onChange={(event) => setCompletedFilter(event.target.value)}><option value="false">Pending</option><option value="true">Completed</option><option value="">All tasks</option></select></label></div>
      {error && <div className="mb-4"><ErrorState message={error} /></div>}
      {!tasks && <LoadingState message="Loading tasks…" />}
      {tasks?.length === 0 && <NoData>No tasks match this status.</NoData>}
      {tasks?.length > 0 && <div className="space-y-3">{tasks.map((task) => (
        <article className={`card flex gap-4 ${task.completed ? 'opacity-65' : ''}`} key={task.id}>
          <input className="mt-1 h-5 w-5 shrink-0 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" type="checkbox" checked={task.completed} disabled={updating === task.id} onChange={() => toggle(task)} aria-label={`Mark ${task.title} ${task.completed ? 'pending' : 'completed'}`} />
          <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className={`font-semibold ${task.completed ? 'line-through' : ''}`}>{task.title}</h3><span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold">{task.priority}</span></div><p className="mt-1 text-sm leading-6 text-slate-500">{task.description}</p><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400"><span>Deadline: {task.normalized_deadline || task.raw_deadline || 'None'}</span><span>From: {task.source_email?.subject || 'Unknown email'}</span></div></div>
        </article>
      ))}</div>}
    </div>
  )
}

