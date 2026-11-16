export const DEFAULT_CUTOFF = '2027-02-08'
export function cutoffTimestamp(date) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new Error('Select a valid cutoff date')
  return `${date}T23:59:59.999999Z`
}
export function formatProbability(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : 'Not scored'
}
export async function requestJSON(path, options = {}) {
  const response = await fetch(`/api/v1/research/database${path}`, options)
  let body
  try { body = await response.json() } catch { throw new Error('Invalid API response. Check that the local research backend is running.') }
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map(item => item.msg || 'Invalid request').join('; ') : body.detail
    throw new Error(body.error?.message || detail || `Request failed (${response.status})`)
  }
  return body
}

export async function assessEnrollments(enrollments, date) {
  const cutoff = encodeURIComponent(cutoffTimestamp(date))
  const pairs = await Promise.all(enrollments.map(async enrollment => {
    try {
      const result = await requestJSON(`/enrollments/${enrollment.enrollment_id}/risk-assessment?cutoff=${cutoff}`)
      return [enrollment.enrollment_id, result]
    } catch (error) {
      if (error.name === 'AbortError') throw error
      return [enrollment.enrollment_id, {status:'request_error', reason:error.message, research_risk_probability:null, evidence:{}, coverage:{}}]
    }
  }))
  return Object.fromEntries(pairs)
}
export function formatChange(value) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value > 0 ? '+' : ''}${value}` : 'Unknown'
}
