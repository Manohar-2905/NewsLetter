import React, { useState } from 'react'
import { Code, Eye, FileText, Mail } from 'lucide-react'
import EmptyState from './EmptyState'

const previewTabs = [
  { id: 'preview', label: 'Preview', icon: Eye },
  { id: 'html', label: 'HTML', icon: Code },
  { id: 'markdown', label: 'Markdown', icon: FileText },
]

function NewsletterPreview({ newsletter }) {
  const [activeTab, setActiveTab] = useState('preview')

  if (!newsletter?.html) {
    return <EmptyState icon={Mail} title='No draft yet' text='The newsletter preview appears here after the writing step.' />
  }

  return (
    <div className='space-y-4'>
      <div className='rounded-xl border-gradient p-4'>
        <p className='text-[11px] uppercase tracking-wider text-neutral-500'>Subject · simulated email</p>
        <p className='mt-1 font-semibold text-white'>{newsletter.subject}</p>
      </div>
      <div role='tablist' className='inline-flex gap-1 p-1 rounded-lg bg-jet-700 border border-white/[0.06]'>
        {previewTabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type='button'
            role='tab'
            aria-selected={activeTab === id}
            onClick={() => setActiveTab(id)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium duration-200 ${
              activeTab === id ? 'bg-cerulean text-white' : 'text-neutral-400 hover:text-white'
            }`}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>
      {activeTab === 'preview' && (
        // Sandboxed: newsletter HTML can't run scripts; links open in a new tab.
        <iframe
          title='Newsletter preview'
          srcDoc={newsletter.html}
          sandbox='allow-popups allow-popups-to-escape-sandbox'
          className='w-full h-[680px] rounded-xl border border-white/10 bg-white'
        />
      )}
      {activeTab !== 'preview' && (
        <pre className='scrollbar-thin w-full h-[680px] overflow-auto rounded-xl bg-jet border border-white/[0.06] text-neutral-300 p-4 text-xs whitespace-pre-wrap'>
          {activeTab === 'html' ? newsletter.html : newsletter.markdown}
        </pre>
      )}
    </div>
  )
}

export default NewsletterPreview
