import { useCallback, useEffect, useRef, useState } from 'react'
import agentService from '../services/agentService'

const TERMINAL = ['completed', 'completed_with_issues', 'no_results', 'failed']
const STORAGE_KEY = 'newsletter-agent:last-run'

function remember(runId) {
    try {
        if (runId) localStorage.setItem(STORAGE_KEY, runId)
        else localStorage.removeItem(STORAGE_KEY)
    } catch {
        // storage may be blocked; the run still lives on the backend
    }
}

function recall() {
    try {
        return localStorage.getItem(STORAGE_KEY)
    } catch {
        return null
    }
}

// Follows a backend run: real progress events via Server-Sent Events,
// with polling as a fallback if the stream drops.
export default function useAgentRun() {
    const [run, setRun] = useState(null)
    const [events, setEvents] = useState([])
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)
    const sourceRef = useRef(null)
    const pollRef = useRef(null)
    const eventsRef = useRef([])

    const stopListening = useCallback(() => {
        sourceRef.current?.close()
        sourceRef.current = null
        clearInterval(pollRef.current)
        pollRef.current = null
    }, [])

    const refresh = useCallback(async (runId) => {
        const data = await agentService.getRun(runId)
        setRun(data)
        eventsRef.current = data.events || []
        setEvents(eventsRef.current)
        return data
    }, [])

    const startPolling = useCallback((runId) => {
        clearInterval(pollRef.current)
        pollRef.current = setInterval(async () => {
            try {
                const data = await refresh(runId)
                if (TERMINAL.includes(data.status) || data.status === 'awaiting_approval') {
                    clearInterval(pollRef.current)
                }
            } catch (err) {
                setError(err.message)
                clearInterval(pollRef.current)
            }
        }, 2000)
    }, [refresh])

    const listen = useCallback((runId) => {
        stopListening()
        const source = new EventSource(agentService.eventsUrl(runId, eventsRef.current.length))
        sourceRef.current = source

        source.addEventListener('progress', (e) => {
            const event = JSON.parse(e.data)
            eventsRef.current = [...eventsRef.current, event]
            setEvents(eventsRef.current)
        })
        source.addEventListener('status', () => {
            refresh(runId).catch(() => {})
        })
        source.addEventListener('end', () => {
            stopListening()
            refresh(runId).catch((err) => setError(err.message))
        })
        source.onerror = () => {
            // Stream interrupted: fall back to polling the status endpoint.
            source.close()
            sourceRef.current = null
            startPolling(runId)
        }
    }, [refresh, startPolling, stopListening])

    const start = useCallback(async (payload) => {
        setError('')
        setBusy(true)
        stopListening()
        eventsRef.current = []
        setEvents([])
        setRun(null)
        try {
            const { run_id } = await agentService.startRun(payload)
            remember(run_id)
            await refresh(run_id)
            listen(run_id)
        } catch (err) {
            setError(err.message)
        } finally {
            setBusy(false)
        }
    }, [listen, refresh, stopListening])

    const approve = useCallback(async () => {
        if (!run) return
        setError('')
        setBusy(true)
        try {
            setRun(await agentService.approve(run.run_id))
            listen(run.run_id)
        } catch (err) {
            setError(err.message)
        } finally {
            setBusy(false)
        }
    }, [listen, run])

    const revise = useCallback(async (feedback) => {
        if (!run) return
        setError('')
        setBusy(true)
        try {
            setRun(await agentService.revise(run.run_id, feedback))
            listen(run.run_id)
        } catch (err) {
            setError(err.message)
        } finally {
            setBusy(false)
        }
    }, [listen, run])

    // Open an existing run (e.g. from the Runs page) and follow it if still active.
    const open = useCallback(async (runId) => {
        setError('')
        stopListening()
        try {
            const data = await refresh(runId)
            remember(runId)
            if (!TERMINAL.includes(data.status) && data.status !== 'awaiting_approval') listen(runId)
        } catch (err) {
            setError(err.message)
        }
    }, [listen, refresh, stopListening])

    const reset = useCallback(() => {
        stopListening()
        remember(null)
        eventsRef.current = []
        setEvents([])
        setRun(null)
        setError('')
    }, [stopListening])

    const deleteRun = useCallback(async (runId) => {
        const idToDelete = runId || run?.run_id
        if (!idToDelete) return
        setError('')
        setBusy(true)
        try {
            await agentService.deleteRun(idToDelete)
            if (run?.run_id === idToDelete || !runId) {
                reset()
            }
        } catch (err) {
            setError(err.message)
            throw err
        } finally {
            setBusy(false)
        }
    }, [reset, run])

    // Restore the last run after a page reload (state lives on the backend).
    useEffect(() => {
        const last = recall()
        if (!last) return
        refresh(last)
            .then((data) => {
                if (!TERMINAL.includes(data.status) && data.status !== 'awaiting_approval') listen(last)
            })
            .catch(() => remember(null))
        return stopListening
    }, [listen, refresh, stopListening])

    const isRunning = Boolean(run) && ['queued', 'running'].includes(run.status)

    return { run, events, error, busy, isRunning, start, approve, revise, open, reset, deleteRun }
}
