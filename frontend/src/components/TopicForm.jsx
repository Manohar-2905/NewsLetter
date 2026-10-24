import React from 'react'
import { LoaderCircle, Play, Sparkles, X } from 'lucide-react'
import Button from './Button'

const suggestedTopics = [
  'Latest developments in Agentic AI and autonomous coding agents',
  'Generative AI product launches this week',
  'Cybersecurity threats and data breaches',
  'Software engineering and developer tools',
  'Startup funding and acquisitions in India',
  'Climate tech and renewable energy',
]

function TopicForm({ goal, setGoal, onSubmit, disabled, running }) {
  const handleSubmit = (e) => {
    e.preventDefault()
    if (!disabled) onSubmit()
  }

  return (
    <form onSubmit={handleSubmit} className='space-y-4'>
      <div>
        <label htmlFor='goal' className='block mb-1.5 text-xs font-medium text-neutral-400'>
          What should the newsletter cover?
        </label>
        <div className='relative'>
          <textarea
            id='goal'
            rows={3}
            maxLength={500}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder='e.g. Create a newsletter about the latest developments in Agentic AI and autonomous coding agents'
            className={`w-full px-3 py-2.5 rounded-lg border border-white/10 bg-jet-700 text-sm text-neutral-100 placeholder:text-neutral-500 outline-none focus:border-cerulean-400 resize-y duration-200 ${
              goal ? 'pr-9' : ''
            }`}
          />
          {goal ? (
            <button
              type='button'
              aria-label='Clear goal'
              onClick={() => setGoal('')}
              className='absolute top-2 right-2 inline-flex h-6 w-6 items-center justify-center rounded-md text-neutral-400 hover:bg-white/10 hover:text-neutral-100'
            >
              <X size={14} />
            </button>
          ) : null}
        </div>
      </div>
      <div className='flex flex-wrap gap-2'>
        {suggestedTopics.map((topic) => (
          <button
            key={topic}
            type='button'
            onClick={() => setGoal(topic)}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs border duration-200 ${
              goal === topic
                ? 'border-rose/60 bg-rose/10 text-rose-300'
                : 'border-white/10 text-neutral-400 hover:border-cerulean-400 hover:text-cerulean-300'
            }`}
          >
            <Sparkles size={11} />
            {topic}
          </button>
        ))}
      </div>
      <Button type='submit' variant='accent' disabled={disabled} className='w-full py-2.5'>
        {running ? <LoaderCircle size={16} className='animate-spin' /> : <Play size={16} />}
        {running ? 'Agent running…' : 'Run Agent'}
      </Button>
    </form>
  )
}

export default TopicForm
