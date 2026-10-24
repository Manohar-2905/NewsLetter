import React from 'react'
import { BadgeCheck, Eye, Link2, Lock, ShieldAlert, Wallet } from 'lucide-react'
import Container from '../container/Container'
import SectionHeading from './SectionHeading'

const features = [
  { title: 'Real articles only', icon: Link2, text: 'Never asks a model to invent news. If too few reliable sources exist, it returns fewer articles and says why.' },
  { title: 'Source-grounded', icon: BadgeCheck, text: 'Headlines and links come straight from publishers. Every summary links to its original.' },
  { title: 'Self-critique', icon: ShieldAlert, text: 'Deterministic checks plus an AI reviewer. Failed reviews trigger a revision, not a cover-up.' },
  { title: 'Transparent by design', icon: Eye, text: 'Missing dates, excerpt-only summaries and unresolved issues are disclosed inside the newsletter.' },
  { title: 'Free-first models', icon: Wallet, text: 'Gemini free tier by default, optional local Ollama. Never switches to a paid provider silently.' },
  { title: 'Safe with web content', icon: Lock, text: 'Scraped text is treated as untrusted. Respects robots.txt and paywalls, and ignores instructions hidden in articles.' },
]

function FeatureGrid() {
  return (
    <section className='py-24 bg-jet-800/40 border-y border-white/5'>
      <Container>
        <SectionHeading
          eyebrow='Why trust it'
          title='Accuracy over volume'
          text='The agent is built to be honest about what it found, and about what it could not verify.'
        />
        <div className='mt-14 grid md:grid-cols-2 lg:grid-cols-3 gap-px rounded-2xl overflow-hidden border border-white/[0.07] bg-white/[0.07]'>
          {features.map((feature) => {
            const Icon = feature.icon
            return (
              <div key={feature.title} className='p-7 bg-jet-800 hover:bg-jet-700 duration-300'>
                <Icon size={22} className='text-rose' />
                <h3 className='mt-4 font-semibold text-white'>{feature.title}</h3>
                <p className='mt-2 text-sm text-neutral-400 leading-relaxed'>{feature.text}</p>
              </div>
            )
          })}
        </div>
      </Container>
    </section>
  )
}

export default FeatureGrid
