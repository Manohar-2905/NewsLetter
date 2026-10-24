import React from 'react'
import { CircleAlert, CircleCheck, CircleX, LoaderCircle, Search, UserCheck } from 'lucide-react'

const bannerStyles = {
  queued: { icon: LoaderCircle, spin: true, className: 'border-cerulean/40 bg-cerulean/10 text-cerulean-300', title: 'Starting the agent…' },
  running: { icon: LoaderCircle, spin: true, className: 'border-cerulean/40 bg-cerulean/10 text-cerulean-300', title: 'Agent is working' },
  awaiting_approval: { icon: UserCheck, className: 'border-rose/40 bg-rose/10 text-rose-300', title: 'Draft ready for review' },
  completed: { icon: CircleCheck, className: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300', title: 'Newsletter ready (simulated send)' },
  completed_with_issues: { icon: CircleAlert, className: 'border-amber-400/30 bg-amber-400/10 text-amber-300', title: 'Saved with unresolved review issues' },
  no_results: { icon: Search, className: 'border-amber-400/30 bg-amber-400/10 text-amber-300', title: 'Not enough reliable articles found' },
  failed: { icon: CircleX, className: 'border-red-500/30 bg-red-500/10 text-red-400', title: 'Run failed' },
}

function StatusBanner({ run, error }) {
  if (error) {
    return (
      <div role='alert' className='flex items-start gap-2 p-3 rounded-xl border border-red-500/30 bg-red-500/10 text-red-300 text-sm'>
        <CircleX size={18} className='shrink-0 mt-0.5' />
        <span>{error}</span>
      </div>
    )
  }
  if (!run) return null

  const style = bannerStyles[run.status] || bannerStyles.running
  const Icon = style.icon
  const detail = run.error || run.result?.message || run.message

  return (
    <div role='status' className={`flex items-start gap-2.5 p-3 rounded-xl border text-sm ${style.className}`}>
      <Icon size={18} className={`shrink-0 mt-0.5 ${style.spin ? 'animate-spin' : ''}`} />
      <div>
        <p className='font-medium'>{style.title}</p>
        {detail && <p className='text-xs mt-0.5 text-neutral-300'>{detail}</p>}
        {run.result?.llm_calls != null && (
          <p className='text-xs mt-0.5 text-neutral-500'>Model requests used: {run.result.llm_calls}</p>
        )}
      </div>
    </div>
  )
}

export default StatusBanner
