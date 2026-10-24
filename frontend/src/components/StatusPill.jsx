import React from 'react'

const statusStyles = {
  queued: { label: 'Queued', className: 'bg-cerulean/15 text-cerulean-300' },
  running: { label: 'Running', className: 'bg-cerulean/15 text-cerulean-300' },
  awaiting_approval: { label: 'Needs approval', className: 'bg-rose/15 text-rose-300' },
  completed: { label: 'Completed', className: 'bg-emerald-400/10 text-emerald-300' },
  completed_with_issues: { label: 'With issues', className: 'bg-amber-400/10 text-amber-300' },
  no_results: { label: 'No results', className: 'bg-amber-400/10 text-amber-300' },
  failed: { label: 'Failed', className: 'bg-red-500/10 text-red-400' },
}

function StatusPill({ status }) {
  const style = statusStyles[status] || { label: status, className: 'bg-white/5 text-neutral-400' }
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium whitespace-nowrap ${style.className}`}>
      {style.label}
    </span>
  )
}

export default StatusPill
