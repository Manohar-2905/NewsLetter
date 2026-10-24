import { createContext, useContext } from "react"

// Same pattern as TodoContext in chai-aur-react:
// default shape here, real values are provided by <AgentProvider value={...}> in App.jsx
export const AgentContext = createContext({
    run: null,
    events: [],
    error: "",
    busy: false,
    isRunning: false,
    startRun: (_payload) => {},
    approveDraft: () => {},
    reviseDraft: (_feedback) => {},
    openRun: (_runId) => {},
    resetRun: () => {},
    deleteRun: (_runId) => {},
})

export const useAgent = () => {
    return useContext(AgentContext)
}

export const AgentProvider = AgentContext.Provider
