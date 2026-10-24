import React from 'react'

function Logo({ width = '36px', showText = true }) {
  return (
    <div className='flex items-center gap-2.5'>
      <svg width={width} height={width} viewBox='0 0 40 40' fill='none' aria-hidden='true'>
        <rect x='1' y='1' width='38' height='38' rx='10' fill='#111111' stroke='url(#logoStroke)' strokeWidth='1.5' />
        <path d='M11 28V12l9 10 9-10v16' stroke='url(#logoStroke)' strokeWidth='2.6' strokeLinecap='round' strokeLinejoin='round' />
        <circle cx='29' cy='12' r='2.6' fill='#ff2d95' />
        <defs>
          <linearGradient id='logoStroke' x1='0' y1='0' x2='40' y2='40'>
            <stop stopColor='#26a6d9' />
            <stop offset='1' stopColor='#ff2d95' />
          </linearGradient>
        </defs>
      </svg>
      {showText && (
        <span className='font-display text-lg font-semibold tracking-tight text-white'>
          Newsletter<span className='text-rose'>Agent</span>
        </span>
      )}
    </div>
  )
}

export default Logo
