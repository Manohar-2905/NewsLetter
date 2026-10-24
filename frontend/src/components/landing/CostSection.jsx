import React from 'react'
import Container from '../container/Container'
import SectionHeading from './SectionHeading'

const costRows = [
  { service: 'Google News RSS · GDELT · publisher RSS · Hacker News', cost: 'Free', note: 'No key needed; public rate limits apply', tone: 'free' },
  { service: 'Google Gemini (default)', cost: 'Free tier', note: 'Daily quotas set per project; charged beyond that only if billing is enabled', tone: 'quota' },
  { service: 'Ollama (local, optional)', cost: 'Free', note: 'Runs on your computer; needs enough RAM/GPU', tone: 'free' },
  { service: 'OpenAI (optional)', cost: 'Paid', note: 'Billed per token; a ChatGPT subscription does not include API credits', tone: 'paid' },
]

const toneClass = {
  free: 'bg-cerulean/15 text-cerulean-300',
  quota: 'bg-white/10 text-neutral-200',
  paid: 'bg-rose/15 text-rose-300',
}

function CostSection() {
  return (
    <section className='py-24 bg-jet-800/40 border-y border-white/5'>
      <Container className='grid lg:grid-cols-5 gap-12 items-start'>
        <div className='lg:col-span-2'>
          <SectionHeading
            align='left'
            eyebrow='Honest costs'
            title='Free where it can be, clear where it cannot'
            text='Research never needs a paid key. Model usage depends on the provider you choose, and the agent tells you when a quota runs out instead of quietly switching.'
          />
        </div>
        <div className='lg:col-span-3 rounded-2xl border border-white/[0.07] overflow-hidden'>
          <table className='w-full text-sm'>
            <thead className='bg-jet-700 text-left text-xs uppercase tracking-wider text-neutral-500'>
              <tr>
                <th className='px-5 py-3 font-medium'>Service</th>
                <th className='px-5 py-3 font-medium'>Cost</th>
              </tr>
            </thead>
            <tbody className='divide-y divide-white/5 bg-jet-800'>
              {costRows.map((row) => (
                <tr key={row.service}>
                  <td className='px-5 py-4'>
                    <p className='text-neutral-100'>{row.service}</p>
                    <p className='text-xs text-neutral-500 mt-0.5'>{row.note}</p>
                  </td>
                  <td className='px-5 py-4 whitespace-nowrap'>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${toneClass[row.tone]}`}>{row.cost}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Container>
    </section>
  )
}

export default CostSection
