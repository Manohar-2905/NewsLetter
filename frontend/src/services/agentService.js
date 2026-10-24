import conf from '../conf/conf.js'

// Talks to the FastAPI backend. Same pattern as the Appwrite services in
// chai-aur-react: one class, one exported instance.
export class AgentService {
    baseUrl = conf.apiBaseUrl

    async request(path, options = {}) {
        let response
        try {
            response = await fetch(`${this.baseUrl}${path}`, {
                headers: { 'Content-Type': 'application/json' },
                ...options,
            })
        } catch (error) {
            console.log('AgentService :: request :: error', error)
            throw new Error('Cannot reach the backend. Is it running on port 8000?')
        }
        const data = await response.json().catch(() => ({}))
        if (!response.ok) {
            throw new Error(formatError(data, response.status))
        }
        return data
    }

    getConfig() {
        return this.request('/api/config')
    }

    startRun(payload) {
        return this.request('/api/agent/run', { method: 'POST', body: JSON.stringify(payload) })
    }

    getRuns(limit = 30) {
        return this.request(`/api/agent/runs?limit=${limit}`)
    }

    getRun(runId) {
        return this.request(`/api/agent/${runId}`)
    }

    approve(runId) {
        return this.request(`/api/agent/${runId}/approve`, { method: 'POST' })
    }

    revise(runId, feedback) {
        return this.request(`/api/agent/${runId}/revise`, {
            method: 'POST',
            body: JSON.stringify({ feedback }),
        })
    }

    eventsUrl(runId, after = 0) {
        return `${this.baseUrl}/api/agent/${runId}/events?after=${after}`
    }

    downloadUrl(runId, format) {
        return `${this.baseUrl}/api/agent/${runId}/download?format=${format}`
    }

    deleteRun(runId) {
        return this.request(`/api/agent/${runId}`, { method: 'DELETE' })
    }
}

function formatError(data, status) {
    const detail = data?.detail
    if (Array.isArray(detail)) {
        // Pydantic validation errors
        return detail.map((d) => d.msg?.replace(/^Value error, /, '')).join(' ')
    }
    if (typeof detail === 'string') return detail
    return `Request failed (HTTP ${status})`
}

const agentService = new AgentService()

export default agentService
