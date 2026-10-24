import React from 'react'

const VARIANTS = {
  primary: 'bg-cerulean text-white hover:bg-cerulean-600 disabled:bg-cerulean/30 disabled:text-white/50',
  accent: 'bg-rose text-jet font-semibold hover:bg-rose-400 disabled:bg-rose/30 disabled:text-jet/60',
  secondary: 'bg-white/5 text-neutral-200 border border-white/10 hover:bg-white/10 disabled:text-neutral-500',
  ghost: 'text-neutral-400 hover:text-white hover:bg-white/5',
  danger: 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 hover:text-red-300 disabled:opacity-50',
}

export default function Button({
  children,
  type = 'button',
  variant = 'primary',
  className = '',
  ...props
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium duration-200 disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
