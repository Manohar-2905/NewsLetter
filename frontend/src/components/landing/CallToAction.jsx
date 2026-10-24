import React from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import Container from '../container/Container'

function CallToAction() {
  const navigate = useNavigate()

  return (
    <section className='py-24'>
      <Container>
        <div className='relative overflow-hidden rounded-3xl border border-white/10 px-6 py-16 sm:px-16 text-center bg-jet-800'>
          <div className='absolute -left-24 -top-24 size-72 rounded-full bg-cerulean/25 blur-[100px]' />
          <div className='absolute -right-24 -bottom-24 size-72 rounded-full bg-rose/20 blur-[100px]' />
          <div className='relative'>
            <h2 className='font-display text-3xl sm:text-4xl font-semibold tracking-tight text-white'>
              Ready for your first issue?
            </h2>
            <p className='mt-4 text-neutral-400 max-w-xl mx-auto'>
              Pick a topic, choose autonomous or human-in-the-loop, and watch every step happen live.
            </p>
            <button
              onClick={() => navigate('/agent')}
              className='mt-8 inline-flex items-center gap-2 px-6 py-3 rounded-full bg-rose text-jet font-semibold hover:bg-rose-400 duration-200 shadow-[0_0_40px_-8px_rgba(255,45,149,0.6)]'
            >
              Open the agent <ArrowRight size={18} />
            </button>
          </div>
        </div>
      </Container>
    </section>
  )
}

export default CallToAction
