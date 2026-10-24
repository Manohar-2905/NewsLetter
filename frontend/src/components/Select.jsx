import React, { useId } from 'react'

function Select({ options = [], label, className = '', ...props }, ref) {
  const id = useId()
  return (
    <div className='w-full'>
      {label && (
        <label htmlFor={id} className='block mb-1.5 text-xs font-medium text-neutral-400'>
          {label}
        </label>
      )}
      <select
        {...props}
        id={id}
        ref={ref}
        className={`w-full px-3 py-2 rounded-lg bg-jet-700 text-sm text-neutral-200 border border-white/10 outline-none focus:border-cerulean-400 disabled:opacity-60 duration-200 ${className}`}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}

export default React.forwardRef(Select)
