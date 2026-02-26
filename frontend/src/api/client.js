const BASE = '/api'

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.status = status
    this.data = data
  }
}

export async function apiFetch(endpoint, options = {}) {
  const url = `${BASE}${endpoint}`
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  }

  if (config.body && typeof config.body === 'object' && !(config.body instanceof Blob)) {
    config.body = JSON.stringify(config.body)
  }

  const res = await fetch(url, config)

  if (options.responseType === 'blob') {
    if (!res.ok) {
      const text = await res.text()
      throw new ApiError(text || res.statusText, res.status)
    }
    return res.blob()
  }

  const data = res.status === 204 ? null : await res.json()

  if (!res.ok) {
    throw new ApiError(data?.error || res.statusText, res.status, data)
  }

  return data
}
