import { useEffect, useState } from 'react'
import agentService from '../services/agentService'

// Loads non-secret backend configuration (available providers, warnings).
export default function useAppConfig() {
    const [config, setConfig] = useState(null)
    const [error, setError] = useState('')

    useEffect(() => {
        agentService
            .getConfig()
            .then(setConfig)
            .catch((err) => setError(err.message))
    }, [])

    return { config, error }
}
