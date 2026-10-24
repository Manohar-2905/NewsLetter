import React from 'react'

function Card({ title, icon: Icon, actions, children, className = '', bodyClassName = '' }) {
  return (
    <section className={`rounded-2xl border border-white/[0.07] bg-jet-800 ${className}`}>
      {title && (
        <div className='flex items-center justify-between gap-2 px-5 py-3.5 border-b border-white/[0.06] shrink-0'>
          <h2 className='flex items-center gap-2 text-sm font-semibold text-white'>
            {Icon && <Icon size={16} className='text-cerulean-400' />}
            {title}
          </h2>
          {actions}
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </section>
  )
}

export default Card
