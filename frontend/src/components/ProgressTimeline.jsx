import React, { useMemo, useState } from 'react'
import {
  Brain,
  Check,
  Circle,
  CircleAlert,
  Filter,
  LoaderCircle,
  PenLine,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  UserCheck,
  FileText,
  ListOrdered,
  X,
} from 'lucide-react'

const STEPS = [
  { id: 'planning', label: 'Planning', icon: Brain },
  { id: 'research', label: 'Research', icon: Search },
  { id: 'ranking', label: 'Query ranking', icon: ListOrdered },
  { id: 'selection', label: 'Article selection', icon: Filter },
  { id: 'summarization', label: 'Summarization', icon: FileText },
  { id: 'writing', label: 'Writing', icon: PenLine },
  { id: 'review', label: 'Self-review', icon: ShieldCheck },
  { id: 'revision', label: 'Revision', icon: RefreshCw, optional: true },
  { id: 'approval', label: 'Human approval', icon: UserCheck, optional: true },
  { id: 'saving', label: 'Saving & sending', icon: Save },
]

// Derive each step's state from REAL backend events (no simulated progress).
function stepStates(events, runStatus) {
  const states = {}
  for (const e of events) {
    const current = states[e.step]
    if (e.status === 'started') states[e.step] = 'active'
    else if (e.status === 'completed') states[e.step] = 'done'
    else if (e.status === 'failed') states[e.step] = 'failed'
    else if (e.status === 'waiting') states[e.step] = 'waiting'
    else if (e.status === 'warning' && current !== 'done') states[e.step] = current || 'warning'
    else if (!current) states[e.step] = 'active'
  }
  if (states.review === 'warning') states.review = 'done-warn'
  const finished = ['completed', 'completed_with_issues', 'no_results', 'failed'].includes(runStatus)
  if (finished) {
    for (const key of Object.keys(states)) if (states[key] === 'active') states[key] = 'done'
  }
  return states
}

function StateIcon({ state }) {
  if (state === 'active') return <LoaderCircle size={16} className='animate-spin text-rose' />
  if (state === 'done') return <Check size={16} className='text-cerulean-400' />
  if (state === 'done-warn' || state === 'warning') return <CircleAlert size={16} className='text-amber-400' />
  if (state === 'waiting') return <UserCheck size={16} className='text-rose animate-pulse-soft' />
  if (state === 'failed') return <X size={16} className='text-red-500' />
  return <Circle size={16} className='text-neutral-700' />
}

function ProgressTimeline({ events = [], runStatus }) {
  const [showLog, setShowLog] = useState(false)
  const states = useMemo(() => stepStates(events, runStatus), [events, runStatus])
  const lastMessage = useMemo(() => {
    const step = {}
    for (const e of events) step[e.step] = e.message
    return step
  }, [events])

  const visible = STEPS.filter((s) => !s.optional || states[s.id])

  return (
    <div>
      <ol className='relative space-y-3'>
        <span className='absolute left-[7px] top-2 bottom-2 w-px bg-white/[0.06]' aria-hidden='true' />
        {visible.map(({ id, label, icon: Icon }) => (
          <li key={id} className='relative flex items-start gap-3'>
            <span className='mt-0.5 bg-jet-800 rounded-full'>
              <StateIcon state={states[id]} />
            </span>
            <div className='min-w-0'>
              <p className={`flex items-center gap-1.5 text-sm font-medium ${states[id] ? 'text-neutral-100' : 'text-neutral-600'}`}>
                <Icon size={14} />
                {label}
              </p>
              {lastMessage[id] && <p className='text-xs text-neutral-500 break-words'>{lastMessage[id]}</p>}
            </div>
          </li>
        ))}
      </ol>
      {events.length > 0 && (
        <div className='mt-4'>
          <button type='button' onClick={() => setShowLog((v) => !v)} className='text-xs text-cerulean-300 hover:text-cerulean-400 hover:underline'>
            {showLog ? 'Hide' : 'Show'} detailed agent log ({events.length} events)
          </button>
          {showLog && (
            <ul className='scrollbar-thin mt-2 max-h-64 overflow-auto rounded-lg bg-jet border border-white/[0.06] text-neutral-300 p-3 text-xs font-mono space-y-1'>
              {events.map((e, i) => (
                <li key={i} className={e.status === 'warning' || e.status === 'failed' ? 'text-amber-300' : ''}>
                  <span className='text-neutral-600'>{new Date(e.ts).toLocaleTimeString()}</span> [{e.step}/{e.status}] {e.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default ProgressTimeline
