import React from 'react'
import { Download, Trash2 } from 'lucide-react'
import Button from './Button'
import agentService from '../services/agentService'

const downloadFormats = [
  { id: 'html', label: 'HTML' },
  { id: 'markdown', label: 'Markdown' },
  { id: 'json', label: 'Sources + review (JSON)' },
]

function DownloadButtons({ runId, output, onDelete, deleting }) {
  if (!output) return null

  return (
    <div className='flex flex-wrap items-center justify-between gap-3'>
      <div className='flex flex-wrap items-center gap-2'>
        {downloadFormats.map((format) => (
          <a
            key={format.id}
            href={agentService.downloadUrl(runId, format.id)}
            download
            className='inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-cerulean/40 text-cerulean-300 hover:bg-cerulean/10 duration-200'
          >
            <Download size={14} /> {format.label}
          </a>
        ))}
        <span className='text-xs text-neutral-500'>Saved on the server as {output.primary_file}</span>
      </div>
      {onDelete && (
        <Button
          variant='danger'
          className='px-2.5! py-1.5! text-xs'
          onClick={onDelete}
          disabled={deleting}
          title='Delete this response'
        >
          <Trash2 size={13} /> {deleting ? 'Deleting…' : 'Delete response'}
        </Button>
      )}
    </div>
  )
}

export default DownloadButtons
