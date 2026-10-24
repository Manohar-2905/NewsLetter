import React from 'react'
import { CircleAlert, CircleCheck, CircleX, Info } from 'lucide-react'
import EmptyState from './EmptyState'

const CHECK_LABELS = {
  article_count: 'Article count',
  no_duplicates: 'No duplicate stories',
  source_links: 'Source links present',
  summaries_present: 'Summaries present',
  numbers_supported: 'Figures found in sources',
  complete: 'All sections present',
  valid_html: 'Valid HTML',
  valid_markdown: 'Valid Markdown',
}

function ReviewReport({ review, history = [], warnings = [] }) {
  if (!review) {
    return <EmptyState icon={Info} title='Not reviewed yet' text='The self-critique report appears after the first draft is written.' />
  }
  const semantic = review.semantic_review || {}

  return (
    <div className='space-y-4 text-sm'>
      <div
        className={`flex flex-wrap items-center gap-2 p-3 rounded-xl border ${
          review.passed ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' : 'border-amber-400/30 bg-amber-400/10 text-amber-300'
        }`}
      >
        {review.passed ? <CircleCheck size={18} /> : <CircleAlert size={18} />}
        <span className='font-medium'>
          {review.passed ? 'Review passed' : `Review found ${review.error_count} issue(s)`}
        </span>
        <span className='text-xs text-neutral-400'>
          ({review.warning_count} warnings, attempt {review.attempt ?? 0})
        </span>
      </div>

      <div className='grid grid-cols-1 sm:grid-cols-2 gap-1'>
        {Object.entries(review.checks || {}).map(([key, ok]) => (
          <p key={key} className='flex items-center gap-2 text-xs text-neutral-300'>
            {ok ? <CircleCheck size={14} className='text-cerulean-400' /> : <CircleX size={14} className='text-rose' />}
            {CHECK_LABELS[key] || key}
          </p>
        ))}
      </div>

      <p className='text-xs text-neutral-500'>
        AI semantic review: <strong className='text-neutral-300'>{semantic.status}</strong>
        {semantic.model && ` by ${semantic.model}`}
        {semantic.reason && `: ${semantic.reason}`}
        {review.scores?.relevance_score != null &&
          ` · relevance ${review.scores.relevance_score}/10 · summary quality ${review.scores.summary_quality}/10`}
      </p>

      {review.issues?.length > 0 && (
        <ul className='space-y-2'>
          {review.issues.map((issue, i) => (
            <li key={i} className='p-2.5 rounded-lg border border-white/[0.07] bg-jet-700/50'>
              <p className='flex items-center gap-2'>
                <span
                  className={`text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded ${
                    issue.severity === 'error' ? 'bg-rose/15 text-rose-300' : 'bg-amber-400/10 text-amber-300'
                  }`}
                >
                  {issue.severity}
                </span>
                <span className='text-neutral-200'>{issue.message}</span>
              </p>
              {issue.fix && <p className='mt-1 text-xs text-neutral-500'>Recommended fix: {issue.fix}</p>}
            </li>
          ))}
        </ul>
      )}

      {history.length > 1 && (
        <div>
          <p className='text-xs font-medium text-neutral-400 mb-1'>Review history</p>
          <ol className='text-xs text-neutral-500 space-y-0.5'>
            {history.map((h, i) => (
              <li key={i}>
                Attempt {h.attempt}: {h.status} ({h.errors} errors, {h.warnings} warnings)
              </li>
            ))}
          </ol>
        </div>
      )}

      {warnings.length > 0 && (
        <div>
          <p className='text-xs font-medium text-neutral-400 mb-1'>Agent warnings</p>
          <ul className='list-disc pl-5 text-xs text-amber-300 space-y-0.5'>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <p className='text-xs text-neutral-600'>{review.disclaimer}</p>
    </div>
  )
}

export default ReviewReport
