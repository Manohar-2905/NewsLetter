import React from 'react'
import { Bot, Check, UserCheck } from 'lucide-react'
import Container from '../container/Container'
import SectionHeading from './SectionHeading'

const modes = [
  {
    name: 'Fully Autonomous',
    icon: Bot,
    accent: 'cerulean',
    text: 'One click: research, write, review, revise and save. Best for regular digests.',
    points: ['Self-reviews and revises up to twice', 'Saves HTML, Markdown and a JSON report', 'Discloses any unresolved issue'],
  },
  {
    name: 'Human-in-the-Loop',
    icon: UserCheck,
    accent: 'rose',
    text: 'The agent pauses with a reviewed draft. You approve it or tell it what to change.',
    points: ['Inspect selected articles and the draft', 'Request changes in plain English', 'Paused runs survive reloads and restarts'],
  },
]

function ModesSection() {
  return (
    <section className='py-24'>
      <Container>
        <SectionHeading eyebrow='Two modes' title='Let it run, or stay in control' />
        <div className='mt-14 grid md:grid-cols-2 gap-6'>
          {modes.map((mode) => {
            const Icon = mode.icon
            const isRose = mode.accent === 'rose'
            return (
              <div
                key={mode.name}
                className={`relative p-8 rounded-2xl border bg-jet-800 ${isRose ? 'border-rose/30' : 'border-cerulean/30'}`}
              >
                <div className={`absolute inset-x-8 -top-px h-px ${isRose ? 'bg-gradient-to-r from-transparent via-rose to-transparent' : 'bg-gradient-to-r from-transparent via-cerulean-400 to-transparent'}`} />
                <span className={`grid place-items-center size-12 rounded-xl ${isRose ? 'bg-rose/10 text-rose' : 'bg-cerulean/10 text-cerulean-300'}`}>
                  <Icon size={22} />
                </span>
                <h3 className='mt-5 font-display text-xl font-semibold text-white'>{mode.name}</h3>
                <p className='mt-2 text-neutral-400'>{mode.text}</p>
                <ul className='mt-6 space-y-2.5'>
                  {mode.points.map((point) => (
                    <li key={point} className='flex items-start gap-2 text-sm text-neutral-300'>
                      <Check size={16} className={`mt-0.5 shrink-0 ${isRose ? 'text-rose' : 'text-cerulean-400'}`} />
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </Container>
    </section>
  )
}

export default ModesSection
