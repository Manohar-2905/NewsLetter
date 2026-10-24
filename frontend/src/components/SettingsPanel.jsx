import React from 'react'
import { Bot, UserCheck } from 'lucide-react'
import Select from './Select'

function ModeToggle({ mode, setMode, disabled }) {
  const options = [
    { value: 'autonomous', label: 'Fully Autonomous', icon: Bot, text: 'Researches, writes, reviews and saves on its own.' },
    { value: 'hitl', label: 'Human-in-the-Loop', icon: UserCheck, text: 'Pauses with a draft for your approval.' },
  ]
  return (
    <div>
      <p className='mb-1.5 text-xs font-medium text-neutral-400'>Execution mode</p>
      <div role='radiogroup' className='grid grid-cols-2 gap-2'>
        {options.map(({ value, label, icon: Icon, text }) => {
          const active = mode === value
          return (
            <button
              key={value}
              type='button'
              role='radio'
              aria-checked={active}
              disabled={disabled}
              onClick={() => setMode(value)}
              className={`text-left p-3 rounded-xl border text-sm duration-200 ${
                active
                  ? value === 'hitl'
                    ? 'border-rose/60 bg-rose/10'
                    : 'border-cerulean-400/70 bg-cerulean/10'
                  : 'border-white/10 hover:bg-white/5'
              } disabled:opacity-60`}
            >
              <span className={`flex items-center gap-2 font-medium ${active ? 'text-white' : 'text-neutral-300'}`}>
                <Icon size={16} className={active ? (value === 'hitl' ? 'text-rose' : 'text-cerulean-300') : 'text-neutral-500'} />
                {label}
              </span>
              <span className='block mt-1 text-xs text-neutral-500'>{text}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function SettingsPanel({ settings, setSettings, providers = [], disabled }) {
  const update = (key) => (e) => setSettings((prev) => ({ ...prev, [key]: e.target.value }))

  const providerOptions = providers.length
    ? providers.map((p) => ({
        value: p.id,
        label: `${p.label} (${p.model})${p.configured ? '' : ', not configured'}`,
        disabled: !p.configured,
      }))
    : [{ value: '', label: 'Server default' }]

  const selectedProvider = providers.find((p) => p.id === settings.provider)

  return (
    <div className='space-y-4'>
      <ModeToggle mode={settings.mode} setMode={(mode) => setSettings((prev) => ({ ...prev, mode }))} disabled={disabled} />
      <div className='grid grid-cols-2 gap-3'>
        <Select
          label='Articles'
          value={settings.article_count}
          onChange={update('article_count')}
          disabled={disabled}
          options={[3, 4, 5, 6, 7].map((n) => ({ value: n, label: `${n} articles` }))}
        />
        <Select
          label='Tone'
          value={settings.tone}
          onChange={update('tone')}
          disabled={disabled}
          options={[
            { value: 'professional', label: 'Professional' },
            { value: 'casual', label: 'Casual' },
            { value: 'technical', label: 'Technical' },
            { value: 'executive', label: 'Executive brief' },
          ]}
        />
        <Select
          label='Format'
          value={settings.output_format}
          onChange={update('output_format')}
          disabled={disabled}
          options={[
            { value: 'html', label: 'HTML email' },
            { value: 'markdown', label: 'Markdown' },
          ]}
        />
        <Select
          label='Time window'
          value={settings.lookback_days}
          onChange={update('lookback_days')}
          disabled={disabled}
          options={[
            { value: '', label: 'Auto (default 7 days)' },
            { value: 1, label: 'Last 24 hours' },
            { value: 3, label: 'Last 3 days' },
            { value: 7, label: 'Last 7 days' },
            { value: 14, label: 'Last 14 days' },
            { value: 30, label: 'Last 30 days' },
          ]}
        />
      </div>
      <Select
        label='Model provider'
        value={settings.provider}
        onChange={update('provider')}
        disabled={disabled}
        options={providerOptions}
      />
      {selectedProvider && <p className='text-xs text-neutral-500 -mt-2'>{selectedProvider.cost_note}</p>}
    </div>
  )
}

export default SettingsPanel
