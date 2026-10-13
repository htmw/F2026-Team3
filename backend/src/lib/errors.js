import { z } from 'zod'
import { logger } from './logger.js'

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

export const badRequest = (message, details) => new ApiError(400, 'bad_request', message, details)
export const unauthorized = (message = 'Sign in to continue.') => new ApiError(401, 'unauthorized', message)
export const forbidden = (message = "You don't have access to this.") => new ApiError(403, 'forbidden', message)
export const notFound = (what = 'Resource') => new ApiError(404, 'not_found', `${what} not found.`)
export const conflict = (message) => new ApiError(409, 'conflict', message)
export const unavailable = (message) => new ApiError(503, 'unavailable', message)

export function notFoundHandler(req, res) {
  res.status(404).json({ error: { code: 'not_found', message: `No route for ${req.method} ${req.path}` } })
}

// Every error leaves the API as { error: { code, message, details? } }.
// eslint-disable-next-line no-unused-vars
export function errorHandler(err, req, res, next) {
  if (err instanceof ApiError) {
    return res.status(err.status).json({ error: { code: err.code, message: err.message, details: err.details } })
  }
  if (err instanceof z.ZodError) {
    const details = err.issues.map((issue) => ({ path: issue.path.join('.'), message: issue.message }))
    const first = details[0]
    const message = first ? `${first.path ? `${first.path}: ` : ''}${first.message}` : 'Invalid request.'
    return res.status(400).json({ error: { code: 'validation_error', message, details } })
  }
  if (err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: { code: 'bad_json', message: 'Request body is not valid JSON.' } })
  }
  if (err.type === 'entity.too.large') {
    return res.status(413).json({ error: { code: 'too_large', message: 'Request body is too large.' } })
  }
  // Postgres constraint violations that slipped past validation.
  if (err.code === '23505') {
    return res.status(409).json({ error: { code: 'conflict', message: 'That record already exists.' } })
  }
  if (err.code === '23503' || err.code === '23514' || err.code === '22P02') {
    return res.status(400).json({ error: { code: 'bad_request', message: 'The request refers to invalid data.' } })
  }
  logger.error('unhandled error', { error: err.message, stack: err.stack, path: req.originalUrl })
  res.status(500).json({ error: { code: 'internal', message: 'Something went wrong on our side.' } })
}
