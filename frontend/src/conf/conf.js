const conf = {
    // Empty string = same origin (Vite dev proxy forwards /api to the backend)
    apiBaseUrl: String(import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, ''),
}

export default conf
