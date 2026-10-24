import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, History, LoaderCircle, RefreshCw, Trash2 } from 'lucide-react'
import { Button, Card, Container, EmptyState, StatusPill } from '../components'
import { useAgent } from '../contexts'
import agentService from '../services/agentService'

function Runs() {
  const navigate = useNavigate()
  const { run: activeRun, openRun, resetRun } = useAgent()
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState(null)
  const [error, setError] = useState('')

  const fetchRuns = () => {
    return agentService
      .getRuns()
      .then((data) => {
        setRuns(data)
        setError('')
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  const handleRefresh = () => {
    setLoading(true)
    fetchRuns()
  }

  useEffect(() => {
    fetchRuns()
  }, [])

  const handleOpen = async (runId) => {
    await openRun(runId)
    navigate('/agent')
  }

  const handleDelete = async (e, runId) => {
    e.stopPropagation()
    const confirmed = window.confirm('Are you sure you want to delete this response? This will permanently remove the newsletter and its saved files.')
    if (!confirmed) return
    setDeletingId(runId)
    try {
      await agentService.deleteRun(runId)
      setRuns((prev) => prev.filter((item) => item.run_id !== runId))
      if (activeRun?.run_id === runId) {
        resetRun()
      }
    } catch (err) {
      alert(err.message || 'Failed to delete response')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <Container className='py-10'>
      <div className='flex flex-wrap items-end justify-between gap-4 mb-6'>
        <div>
          <h1 className='font-display text-3xl font-semibold text-white'>Runs</h1>
          <p className='text-sm text-neutral-500 mt-1'>Every run is stored on the backend, including drafts waiting for approval.</p>
        </div>
        <Button variant='secondary' onClick={handleRefresh} disabled={loading}>
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
        </Button>
      </div>

      <Card>
        {loading && (
          <div className='flex items-center justify-center gap-2 py-10 text-neutral-500 text-sm'>
            <LoaderCircle size={18} className='animate-spin' /> Loading runs…
          </div>
        )}
        {!loading && error && <p className='py-6 text-center text-sm text-red-400'>{error}</p>}
        {!loading && !error && runs.length === 0 && (
          <EmptyState icon={History} title='No runs yet' text='Your first newsletter run will show up here.'>
            <Button variant='accent' onClick={() => navigate('/agent')}>
              Start a run
            </Button>
          </EmptyState>
        )}
        {!loading && !error && runs.length > 0 && (
          <ul className='divide-y divide-white/5 -my-2'>
            {runs.map((item) => (
              <li
                key={item.run_id}
                className='flex items-center justify-between gap-3 py-3 group hover:bg-white/[0.02] px-3 -mx-3 rounded-lg transition-colors'
              >
                <div
                  role='button'
                  tabIndex={0}
                  onClick={() => handleOpen(item.run_id)}
                  onKeyDown={(e) => e.key === 'Enter' && handleOpen(item.run_id)}
                  className='flex-1 min-w-0 cursor-pointer flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4'
                >
                  <div className='flex-1 min-w-0'>
                    <p className='text-sm font-medium text-neutral-100 truncate group-hover:text-cerulean-300 duration-200'>
                      {item.subject || item.goal}
                    </p>
                    <p className='text-xs text-neutral-500 truncate'>
                      {item.subject ? item.goal + ' · ' : ''}
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                  <StatusPill status={item.status} />
                </div>
                <div className='flex items-center gap-1 shrink-0'>
                  <button
                    type='button'
                    onClick={(e) => handleDelete(e, item.run_id)}
                    disabled={deletingId === item.run_id}
                    className='p-2 rounded-lg text-neutral-500 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50 cursor-pointer'
                    title='Delete response'
                    aria-label='Delete response'
                  >
                    <Trash2 size={16} className={deletingId === item.run_id ? 'animate-pulse' : ''} />
                  </button>
                  <button
                    type='button'
                    onClick={() => handleOpen(item.run_id)}
                    className='p-2 text-neutral-600 group-hover:text-rose transition-colors hidden sm:block cursor-pointer'
                    aria-label='Open response'
                  >
                    <ArrowRight size={16} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </Container>
  )
}

export default Runs
