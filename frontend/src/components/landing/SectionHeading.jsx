import React from 'react'

function SectionHeading({ eyebrow, title, text, align = 'center' }) {
  const alignClass = align === 'center' ? 'text-center mx-auto' : 'text-left'
  return (
    <div className={`max-w-2xl ${alignClass}`}>
      {eyebrow && (
        <p className='text-xs font-semibold uppercase tracking-[0.2em] text-rose'>{eyebrow}</p>
      )}
      <h2 className='mt-3 font-display text-3xl sm:text-4xl font-semibold tracking-tight text-white'>{title}</h2>
      {text && <p className='mt-4 text-neutral-400 leading-relaxed'>{text}</p>}
    </div>
  )
}

export default SectionHeading
