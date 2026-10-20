// Base URL of the Acadmate API. Defaults to /api, which the Vite dev server proxies to the backend.
export const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

// Absolute URL for an API path, for links the browser follows itself (e.g. CSV export downloads).
export const apiUrl = (path) => `${API_URL}${path}`

// Sends `body` as JSON by default. Pass `contentType` (e.g. 'text/csv') to send a string or File as-is.
export async function api(path, { method = 'GET', body, signal, contentType } = {}) {
  const hasBody = body !== undefined
  let response
  try {
    response = await fetch(apiUrl(path), {
      method,
      signal,
      credentials: 'include',
      headers: hasBody ? { 'Content-Type': contentType ?? 'application/json' } : undefined,
      body: hasBody ? (contentType ? body : JSON.stringify(body)) : undefined,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError(0, 'network', "Can't reach the Acadmate server. Check your connection and try again.")
  }
  if (response.status === 204) return null
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = data?.error
    throw new ApiError(response.status, error?.code ?? 'error', error?.message ?? `Request failed (${response.status}).`, error?.details)
  }
  return data
}

// Error message plus any per-field details the API attached, for a toast or Notice.
export function errorText(err) {
  const details = Array.isArray(err.details) ? err.details.map((d) => d.message ?? String(d)).filter(Boolean) : []
  return [err.message, ...details].join(' ')
}
