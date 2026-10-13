import rateLimit from 'express-rate-limit'
import { config } from '../config.js'
import { forbidden } from '../lib/errors.js'

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

// CSRF defence in depth on top of SameSite=Lax cookies: a state-changing request that comes from a browser
// must come from one of our own origins. (Requests without an Origin header are not browser form posts.)
export function originCheck(req, res, next) {
  if (SAFE_METHODS.has(req.method)) return next()
  const origin = req.get('origin')
  if (!origin || config.corsOrigins.includes(origin) || origin === config.apiUrl) return next()
  next(forbidden('Cross-site request blocked.'))
}

const limitHandler = (req, res) =>
  res.status(429).json({ error: { code: 'rate_limited', message: 'Too many attempts. Wait a few minutes and try again.' } })

export const authLimiter = rateLimit({
  windowMs: 15 * 60_000,
  limit: config.isTest ? 1000 : 20,
  standardHeaders: 'draft-8',
  legacyHeaders: false,
  handler: limitHandler,
})

export const apiLimiter = rateLimit({
  windowMs: 60_000,
  limit: config.isTest ? 100_000 : 600,
  standardHeaders: 'draft-8',
  legacyHeaders: false,
  handler: limitHandler,
})

// AI advisor questions, per signed-in user (each one can call an external model).
export const aiLimiter = rateLimit({
  windowMs: 60_000,
  limit: config.isTest ? 1000 : 20,
  keyGenerator: (req) => `ai:${req.user.id}`,
  standardHeaders: 'draft-8',
  legacyHeaders: false,
  handler: (req, res) => res.status(429).json({ error: { code: 'rate_limited', message: 'You\'re asking questions too quickly. Wait a minute and try again.' } }),
})
