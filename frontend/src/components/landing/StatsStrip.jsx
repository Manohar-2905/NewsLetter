import React from 'react'
import Container from '../container/Container'

const stats = [
  { value: '5–7', label: 'source-linked articles per issue' },
  { value: '4', label: 'free news sources, no paid search key' },
  { value: '≤ 2', label: 'automatic self-revisions' },
  { value: '~5', label: 'model calls per newsletter' },
]

function StatsStrip() {
  return (
    <section className='border-y border-white/5 bg-jet-800/60'>
      <Container className='grid grid-cols-2 lg:grid-cols-4 divide-x divide-white/5'>
        {stats.map((stat) => (
          <div key={stat.label} className='px-4 py-8 text-center'>
            <p className='font-display text-3xl font-semibold text-white'>{stat.value}</p>
            <p className='mt-1 text-xs text-neutral-500'>{stat.label}</p>
          </div>
        ))}
      </Container>
    </section>
  )
}

export default StatsStrip
