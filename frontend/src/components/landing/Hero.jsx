import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Check, LoaderCircle, Search, Sparkles } from 'lucide-react'
import Container from '../container/Container'

const quickTopics = ['Agentic AI', 'Cybersecurity', 'Startups in India', 'Climate tech']

const previewSteps = [
  { name: 'Plan', detail: '3 queries · last 7 days', state: 'done' },
  { name: 'Research', detail: '42 articles from 4 free sources', state: 'done' },
  { name: 'Select', detail: '6 picked · 9 duplicates removed', state: 'done' },
  { name: 'Summarize', detail: 'grounded in source text', state: 'done' },
  { name: 'Review', detail: 'checking links, figures, relevance', state: 'active' },
  { name: 'Save & send', detail: 'HTML + Markdown', state: 'idle' },
]

function Hero() {
  const navigate = useNavigate()
  const [topic, setTopic] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const goal = topic.trim()
    navigate(goal ? `/agent?goal=${encodeURIComponent(goal)}` : '/agent')
  }

  return (
    <section className='relative overflow-hidden'>
      <div className='absolute -top-40 left-1/2 -translate-x-1/2 h-[520px] w-[900px] rounded-full bg-cerulean/15 blur-[140px] pointer-events-none' />
      <div className='absolute top-40 -right-40 h-80 w-80 rounded-full bg-rose/10 blur-[130px] pointer-events-none' />

      <Container className='relative grid lg:grid-cols-2 gap-14 items-center pt-20 pb-24 lg:pt-28'>
        <div>
          <span className='inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/[0.03] text-xs text-neutral-300'>
            <Sparkles size={13} className='text-rose' />
            Free-first autonomous AI agent
          </span>
          <h1 className='mt-6 font-display text-4xl sm:text-5xl lg:text-6xl font-semibold leading-[1.05] tracking-tight text-white'>
            Your newsletter, <span className='text-gradient'>researched, written and fact-checked</span> by an agent.
          </h1>
          <p className='mt-6 text-lg text-neutral-400 leading-relaxed max-w-xl'>
            Type a topic. The agent plans its research, reads real articles from free news sources, writes a
            source-linked newsletter, critiques its own draft and fixes it before you ever see it.
          </p>

          <form onSubmit={handleSubmit} className='mt-8 max-w-xl'>
            <div className='flex flex-col sm:flex-row gap-2 p-1.5 rounded-2xl border-gradient shadow-[0_0_40px_-10px_rgba(0,123,167,0.5)]'>
              <div className='flex items-center flex-1 gap-2 px-3'>
                <Search size={18} className='text-neutral-500 shrink-0' />
                <input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder='What should your newsletter cover?'
                  aria-label='Newsletter topic'
                  className='w-full bg-transparent py-3 text-sm text-white placeholder:text-neutral-500 outline-none'
                />
              </div>
              <button
                type='submit'
                className='inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-rose text-jet text-sm font-semibold hover:bg-rose-400 duration-200'
              >
                Run the agent <ArrowRight size={16} />
              </button>
            </div>
          </form>

          <div className='mt-4 flex flex-wrap items-center gap-2 text-xs text-neutral-500'>
            <span>Try:</span>
            {quickTopics.map((item) => (
              <button
                key={item}
                onClick={() => setTopic(`Latest news about ${item}`)}
                className='px-3 py-1 rounded-full border border-white/10 text-neutral-300 hover:border-cerulean-400 hover:text-cerulean-300 duration-200'
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        {/* Illustration of the workflow (not live data) */}
        <div className='relative' aria-label='Illustration of the agent workflow'>
          <div className='absolute -inset-4 rounded-3xl bg-gradient-to-br from-cerulean/20 via-transparent to-rose/20 blur-2xl' />
          <div className='relative rounded-2xl border border-white/10 bg-jet-800/90 backdrop-blur shadow-2xl'>
            <div className='flex items-center gap-2 px-4 py-3 border-b border-white/[0.06]'>
              <span className='size-2.5 rounded-full bg-rose' />
              <span className='size-2.5 rounded-full bg-cerulean' />
              <span className='size-2.5 rounded-full bg-neutral-600' />
              <span className='ml-3 text-xs text-neutral-500 font-mono'>example run · “Agentic AI this week”</span>
            </div>
            <ol className='p-5 space-y-3'>
              {previewSteps.map((step, index) => (
                <li key={step.name} className='flex items-center gap-3'>
                  <span
                    className={`grid place-items-center size-7 rounded-lg text-xs font-mono ${
                      step.state === 'done'
                        ? 'bg-cerulean/15 text-cerulean-300'
                        : step.state === 'active'
                          ? 'bg-rose/15 text-rose-300'
                          : 'bg-white/5 text-neutral-600'
                    }`}
                  >
                    {step.state === 'done' ? <Check size={14} /> : step.state === 'active' ? <LoaderCircle size={14} className='animate-spin' /> : index + 1}
                  </span>
                  <div className='flex-1 min-w-0'>
                    <p className={`text-sm font-medium ${step.state === 'idle' ? 'text-neutral-600' : 'text-neutral-100'}`}>{step.name}</p>
                    <p className='text-xs text-neutral-500 truncate'>{step.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
            <div className='mx-5 mb-5 p-4 rounded-xl bg-jet border border-white/[0.06]'>
              <p className='text-[11px] uppercase tracking-wider text-neutral-500'>Subject</p>
              <p className='mt-1 text-sm text-white'>Agentic AI: 6 stories worth your time</p>
              <div className='mt-3 h-1.5 rounded-full bg-gradient-to-r from-cerulean via-cerulean-300 to-rose bg-[length:200%_100%] animate-flow' />
            </div>
          </div>
        </div>
      </Container>
    </section>
  )
}

export default Hero
