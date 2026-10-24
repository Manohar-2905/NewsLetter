import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Activity, CircleAlert, ListChecks, Mail, Newspaper, RotateCcw, Settings2, ShieldCheck, Trash2 } from 'lucide-react'
import {
  ApprovalPanel,
  ArticleList,
  Button,
  Card,
  Container,
  DownloadButtons,
  EmptyState,
  NewsletterPreview,
  ProgressTimeline,
  ReviewReport,
  SettingsPanel,
  StatusBanner,
  TopicForm,
} from '../components'
import { useAgent } from '../contexts'
import useAppConfig from '../hooks/useAppConfig'

const DEFAULT_SETTINGS = {
  mode: 'autonomous',
  article_count: 5,
  tone: 'professional',
  output_format: 'html',
  provider: '',
  lookback_days: '',
}

function Agent() {
  const [searchParams] = useSearchParams()
  const { config, error: configError } = useAppConfig()
  const { run, events, error, busy, isRunning, startRun, approveDraft, reviseDraft, resetRun, deleteRun } = useAgent()
  // null means the field has not been edited yet: the URL `goal` param (below) or a
  // restored run can prefill it once. '' is an explicit clear and must stay empty.
  const [goal, setGoal] = useState(searchParams.get('goal') || null)
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [deleting, setDeleting] = useState(false)

  // Derived values: server default provider, and the goal of a restored run.
  const effectiveSettings = { ...settings, provider: settings.provider || config?.default_provider || '' }
  const shownGoal = goal ?? run?.goal ?? ''

  const handleRun = () => {
    startRun({
      goal: shownGoal,
      mode: settings.mode,
      article_count: Number(settings.article_count),
      tone: settings.tone,
      output_format: settings.output_format,
      provider: effectiveSettings.provider || null,
      lookback_days: settings.lookback_days ? Number(settings.lookback_days) : null,
    })
  }

  const handleReset = () => {
    resetRun()
    setGoal('')
  }

  const handleDeleteResponse = async () => {
    if (!run?.run_id) return
    const confirmed = window.confirm(
      'Are you sure you want to delete this response? This will permanently remove the newsletter and its saved files.'
    )
    if (!confirmed) return
    setDeleting(true)
    try {
      await deleteRun(run.run_id)
      setGoal('')
    } catch (err) {
      alert(err.message || 'Failed to delete response')
    } finally {
      setDeleting(false)
    }
  }

  const result = run?.result || {}
  const articles = result.articles?.length ? result.articles : result.selected || []
  const waitingForApproval = run?.status === 'awaiting_approval'
  const locked = busy || isRunning || waitingForApproval

  return (
    <div className='relative'>
      <div className='absolute inset-x-0 top-0 h-72 bg-gradient-to-b from-cerulean/10 to-transparent pointer-events-none' />
      <Container className='relative py-8 space-y-8'>
        <div className='flex flex-wrap items-end justify-between gap-4'>
          <div>
            <p className='text-xs font-semibold uppercase tracking-[0.2em] text-rose'>Agent workspace</p>
            <h1 className='mt-2 font-display text-3xl font-semibold text-white'>Build a newsletter</h1>
          </div>
        </div>

        {/* Top Section: Goal & Settings on the Left, Agent Progress on the Right */}
        <div className='grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch'>
          {/* Left Column: Goal & Settings */}
          <div className='lg:col-span-6 space-y-6 flex flex-col justify-between'>
            <Card title='Goal' icon={Newspaper}>
              <TopicForm
                goal={shownGoal}
                setGoal={setGoal}
                onSubmit={handleRun}
                disabled={locked || shownGoal.trim().length < 3}
                running={busy || isRunning}
              />
            </Card>

            <Card title='Settings' icon={Settings2}>
              <SettingsPanel
                settings={effectiveSettings}
                setSettings={setSettings}
                providers={config?.providers}
                disabled={locked}
              />
              {configError && <p className='mt-3 text-xs text-red-400'>{configError}</p>}
              {config?.warnings?.length > 0 && (
                <ul className='mt-4 space-y-1.5'>
                  {config.warnings.map((warning) => (
                    <li key={warning} className='flex gap-1.5 text-xs text-amber-300'>
                      <CircleAlert size={14} className='shrink-0 mt-0.5' /> {warning}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          {/* Right Column: Agent Progress */}
          <div className='lg:col-span-6 flex flex-col'>
            <Card
              title='Agent progress'
              icon={Activity}
              className='h-full flex flex-col'
              bodyClassName='flex-1 flex flex-col justify-between'
              actions={
                run && !isRunning ? (
                  <div className='flex items-center gap-1.5'>
                    {!waitingForApproval && (
                      <Button variant='ghost' className='px-2! py-1! text-xs' onClick={handleReset}>
                        <RotateCcw size={14} /> New run
                      </Button>
                    )}
                    <Button
                      variant='danger'
                      className='px-2! py-1! text-xs'
                      onClick={handleDeleteResponse}
                      disabled={busy || deleting}
                      title='Delete response'
                    >
                      <Trash2 size={13} /> {deleting ? 'Deleting…' : 'Delete'}
                    </Button>
                  </div>
                ) : null
              }
            >
              {run || error ? (
                <div className='space-y-5 flex-1 flex flex-col'>
                  <StatusBanner run={run} error={error} />
                  {run && (
                    <div className='flex-1 overflow-y-auto max-h-[520px] scrollbar-thin pr-1'>
                      <ProgressTimeline events={events} runStatus={run.status} />
                    </div>
                  )}
                </div>
              ) : (
                <div className='flex-1 flex items-center justify-center py-10'>
                  <EmptyState
                    icon={Activity}
                    title='Idle'
                    text='Enter a topic and click Run Agent. Real progress from the backend appears here.'
                  />
                </div>
              )}
            </Card>
          </div>
        </div>

        {/* Human-in-the-Loop approval banner (when draft awaits approval) */}
        {waitingForApproval && (
          <ApprovalPanel
            onApprove={approveDraft}
            onRevise={reviseDraft}
            busy={busy}
            rounds={result.human_rounds || 0}
          />
        )}

        {/* Middle Section: Full-width Newsletter */}
        <Card
          title='Newsletter'
          icon={Mail}
          actions={
            run && !isRunning ? (
              <div className='flex items-center gap-2'>
                {result.output ? (
                  <span className='text-xs text-cerulean-300 font-medium px-2 py-0.5 rounded-full bg-cerulean/10 border border-cerulean/30'>
                    Saved
                  </span>
                ) : null}
                <Button
                  variant='danger'
                  className='px-2.5! py-1! text-xs'
                  onClick={handleDeleteResponse}
                  disabled={busy || deleting}
                  title='Delete this response'
                >
                  <Trash2 size={13} /> {deleting ? 'Deleting…' : 'Delete response'}
                </Button>
              </div>
            ) : result.output ? (
              <span className='text-xs text-cerulean-300 font-medium px-2 py-0.5 rounded-full bg-cerulean/10 border border-cerulean/30'>
                Saved
              </span>
            ) : null
          }
        >
          {run?.downloads?.html && (
            <div className='mb-4'>
              <DownloadButtons
                runId={run.run_id}
                output={result.output}
                onDelete={handleDeleteResponse}
                deleting={deleting}
              />
            </div>
          )}
          <NewsletterPreview newsletter={result.newsletter} />
        </Card>

        {/* Bottom Section: Research Results and Quality Review (2 columns) */}
        <div className='grid grid-cols-1 lg:grid-cols-2 gap-6'>
          <Card title='Research results & sources' icon={ListChecks}>
            <ArticleList
              articles={articles}
              summaries={result.summaries}
              researchLog={result.research_log}
              candidatesCount={result.candidates_count}
              researchBrief={result.research_brief}
            />
          </Card>
          <Card title='Quality review' icon={ShieldCheck}>
            <ReviewReport review={result.review} history={result.review_history} warnings={result.warnings} />
          </Card>
        </div>
      </Container>
    </div>
  )
}

export default Agent
