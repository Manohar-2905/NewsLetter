import React from 'react'
import { Brain, FileText, Filter, PenLine, RefreshCw, Save, Search, ShieldCheck } from 'lucide-react'
import Container from '../container/Container'
import SectionHeading from './SectionHeading'

const workflowSteps = [
  { name: 'Plan', icon: Brain, text: 'Turns your goal into search queries, keywords, a time window and quality criteria.' },
  { name: 'Research', icon: Search, text: 'Queries Google News RSS, GDELT, publisher feeds and Hacker News for real articles. Widens the search if results are thin.' },
  { name: 'Select', icon: Filter, text: 'Removes duplicates, scores relevance, recency and source quality, and keeps publishers diverse.' },
  { name: 'Summarize', icon: FileText, text: 'Writes each summary only from the article text, and labels summaries built from a headline or excerpt.' },
  { name: 'Write', icon: PenLine, text: 'Builds an email-ready HTML or Markdown newsletter with every original source link.' },
  { name: 'Review', icon: ShieldCheck, text: 'Checks links, duplicates, format and figures missing from the sources, then asks an AI critic about accuracy.' },
  { name: 'Revise', icon: RefreshCw, text: 'Rewrites or replaces flagged items, up to two times, and discloses anything it could not fix.' },
  { name: 'Save & send', icon: Save, text: 'Saves HTML, Markdown and a JSON report, and shows the subject and content as a simulated send.' },
]

function WorkflowSection() {
  return (
    <section id='how-it-works' className='scroll-mt-20 py-24'>
      <Container>
        <SectionHeading
          eyebrow='How it works'
          title='One click runs a real multi-step agent'
          text='Built with LangGraph: every step is a node, and the agent decides what happens next: broaden the search, revise the draft, or pause for you.'
        />
        <ol className='mt-14 grid sm:grid-cols-2 lg:grid-cols-4 gap-4'>
          {workflowSteps.map((step, index) => {
            const Icon = step.icon
            return (
              <li
                key={step.name}
                className='group relative p-5 rounded-2xl border border-white/[0.07] bg-jet-800 hover:border-cerulean/50 duration-300'
              >
                <div className='flex items-center justify-between'>
                  <span className='grid place-items-center size-10 rounded-xl bg-cerulean/10 text-cerulean-300 group-hover:bg-rose/10 group-hover:text-rose-300 duration-300'>
                    <Icon size={18} />
                  </span>
                  <span className='font-mono text-xs text-neutral-600'>0{index + 1}</span>
                </div>
                <h3 className='mt-4 font-semibold text-white'>{step.name}</h3>
                <p className='mt-2 text-sm text-neutral-400 leading-relaxed'>{step.text}</p>
              </li>
            )
          })}
        </ol>
      </Container>
    </section>
  )
}

export default WorkflowSection
