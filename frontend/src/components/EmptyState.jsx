import React from 'react'
import { Inbox } from 'lucide-react'

function EmptyState({ title = 'Nothing here yet', text = '', icon: Icon = Inbox, children }) {
  return (
    <div className='flex flex-col items-center justify-center text-center py-10'>
      <div className='mb-3 p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]'>
        <Icon size={24} className='text-neutral-500' />
      </div>
      <p className='font-medium text-neutral-300'>{title}</p>
      {text && <p className='text-sm mt-1 max-w-md text-neutral-500'>{text}</p>}
      {children && <div className='mt-4'>{children}</div>}
    </div>
  )
}

export default EmptyState
