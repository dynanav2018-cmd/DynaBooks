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
  const headers = { ...options.headers }

  // Add company header if set
  const company = localStorage.getItem('currentCompany')
  if (company) {
    headers['X-Company'] = company
  }

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  const isFormData = options.body instanceof FormData
  if (!isFormData) {
    headers['Content-Type'] = 'application/json'
  }

  const config = {
    ...options,
    headers,
  }

  if (config.body && typeof config.body === 'object' && !isFormData && !(config.body instanceof Blob)) {
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
