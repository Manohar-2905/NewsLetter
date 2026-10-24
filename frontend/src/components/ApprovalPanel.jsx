import React, { useState } from 'react'
import { Check, MessageSquare, UserCheck } from 'lucide-react'
import Button from './Button'

function ApprovalPanel({ onApprove, onRevise, busy, rounds = 0 }) {
  const [feedback, setFeedback] = useState('')

  const handleFeedback = (e) => {
    e.preventDefault()
    if (feedback.trim().length < 3) return
    onRevise(feedback.trim())
    setFeedback('')
  }

  return (
    <div className='relative overflow-hidden rounded-2xl border border-rose/40 bg-jet-800 p-5 shadow-[0_0_50px_-20px_rgba(255,45,149,0.6)]'>
      <div className='absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-rose to-transparent' />
      <div className='flex items-center gap-2 text-white'>
        <span className='grid place-items-center size-8 rounded-lg bg-rose/15 text-rose'>
          <UserCheck size={16} />
        </span>
        <h2 className='font-semibold'>Your approval is needed</h2>
      </div>
      <p className='mt-3 text-sm text-neutral-400'>
        Check the selected articles and the draft below. Approve it to save and "send", or describe what to change.
        The workflow is paused on the server, so it is safe to reload this page.
        {rounds > 0 && ` (${rounds} change request${rounds > 1 ? 's' : ''} so far)`}
      </p>
      <form onSubmit={handleFeedback} className='mt-4 space-y-3'>
        <textarea
          rows={3}
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          maxLength={2000}
          aria-label='Change request'
          placeholder='e.g. Remove article 3, make the intro shorter and use a more casual tone'
          className='w-full px-3 py-2.5 rounded-lg border border-white/10 bg-jet-700 text-sm text-neutral-100 placeholder:text-neutral-500 outline-none focus:border-rose/60 duration-200'
        />
        <div className='flex flex-wrap gap-2'>
          <Button variant='accent' onClick={onApprove} disabled={busy}>
            <Check size={16} /> Approve & save
          </Button>
          <Button type='submit' variant='secondary' disabled={busy || feedback.trim().length < 3}>
            <MessageSquare size={16} /> Request changes
          </Button>
        </div>
      </form>
    </div>
  )
}

export default ApprovalPanel
