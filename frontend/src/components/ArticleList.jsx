import React from 'react'
import { Calendar, ExternalLink, Newspaper } from 'lucide-react'
import EmptyState from './EmptyState'

const contentBadges = {
  full: { label: 'Full text', className: 'bg-cerulean/15 text-cerulean-300' },
  excerpt_only: { label: 'Excerpt only', className: 'bg-amber-400/10 text-amber-300' },
  title_only: { label: 'Headline only', className: 'bg-amber-400/10 text-amber-300' },
  blocked_by_robots: { label: 'Headline only (robots.txt)', className: 'bg-amber-400/10 text-amber-300' },
}

function formatDate(value) {
  if (!value) return 'Date not available'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date not available' : date.toLocaleDateString(undefined, { dateStyle: 'medium' })
}

function ArticleList({ articles = [], summaries = [], researchLog = [], candidatesCount, researchBrief = '' }) {
  const failedSources = researchLog.filter((entry) => entry.error)

  if (!articles.length) {
    return (
      <EmptyState
        icon={Newspaper}
        title='No articles yet'
        text='Selected articles and their original source links will appear here once research finishes.'
      />
    )
  }

  return (
    <div className='space-y-3'>
      {typeof candidatesCount === 'number' && (
        <p className='text-xs text-neutral-500'>
          {articles.length} selected from {candidatesCount} unique articles found.
          {failedSources.length > 0 && ` ${failedSources.length} source request(s) failed (see agent log).`}
        </p>
      )}
      {researchBrief ? (
        <div className='p-3.5 rounded-xl border border-white/[0.07] bg-jet-700/50'>
          <p className='text-xs font-medium uppercase tracking-wide text-rose mb-2'>Ranked research brief</p>
          <p className='text-sm text-neutral-300 whitespace-pre-wrap leading-relaxed'>{researchBrief}</p>
        </div>
      ) : null}
      <ol className='space-y-3'>
        {articles.map((article, index) => {
          const badge = contentBadges[article.content_status] || contentBadges.title_only
          const summary = summaries?.[index]
          return (
            <li
              key={article.url || index}
              className='p-3.5 rounded-xl border border-white/[0.07] bg-jet-700/50 hover:border-cerulean/40 duration-200'
            >
              <div className='flex items-start justify-between gap-3'>
                <a
                  href={article.url}
                  target='_blank'
                  rel='noopener noreferrer'
                  className='font-medium text-sm text-neutral-100 hover:text-cerulean-300 duration-200'
                >
                  <span className='font-mono text-rose mr-1.5'>{String(index + 1).padStart(2, '0')}</span>
                  {article.title}
                </a>
                <a
                  href={article.url}
                  target='_blank'
                  rel='noopener noreferrer'
                  aria-label='Open original article'
                  className='text-neutral-500 hover:text-rose duration-200'
                >
                  <ExternalLink size={14} />
                </a>
              </div>
              <div className='mt-2 flex flex-wrap items-center gap-2 text-xs text-neutral-500'>
                <span className='text-neutral-300'>{article.publisher}</span>
                <span className='inline-flex items-center gap-1'>
                  <Calendar size={12} /> {formatDate(article.published_at)}
                </span>
                <span className={`px-2 py-0.5 rounded-full ${badge.className}`}>{badge.label}</span>
                {article.source_api && <span className='px-2 py-0.5 rounded-full bg-white/5'>via {article.source_api}</span>}
                {article.scores?.total != null && (
                  <span
                    className='px-2 py-0.5 rounded-full bg-white/5 cursor-help'
                    title={`Relevance: ${article.scores.relevance} · Recency: ${article.scores.recency} · Quality: ${article.scores.quality} · Accessibility: ${article.scores.accessibility ?? '-'} · Corroboration: ${article.scores.corroboration ?? '-'}`}
                  >
                    score {article.scores.total}
                  </span>
                )}
                {article.scores?.corroboration > 0 && (
                  <span
                    className='px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium'
                    title='Corroborated across multiple independent publishers or APIs'
                  >
                    multi-source verified
                  </span>
                )}
              </div>
              {summary && <p className='mt-2 text-sm text-neutral-400 leading-relaxed'>{summary.summary}</p>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export default ArticleList
