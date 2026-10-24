import React, { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Header, Footer } from './components'
import { AgentProvider } from './contexts'
import useAgentRun from './hooks/useAgentRun'

function App() {
  // Run state lives here (like todos in chai-aur-react's App.jsx) so it
  // survives navigation between the landing page and the agent page.
  const { run, events, error, busy, isRunning, start, approve, revise, open, reset, deleteRun } = useAgentRun()
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (!hash) window.scrollTo(0, 0)
  }, [pathname, hash])

  return (
    <AgentProvider
      value={{
        run,
        events,
        error,
        busy,
        isRunning,
        startRun: start,
        approveDraft: approve,
        reviseDraft: revise,
        openRun: open,
        resetRun: reset,
        deleteRun,
      }}
    >
      <div className='min-h-screen flex flex-col bg-jet text-neutral-200'>
        <Header />
        <main className='flex-1'>
          <Outlet />
        </main>
        <Footer />
      </div>
    </AgentProvider>
  )
}

export default App
