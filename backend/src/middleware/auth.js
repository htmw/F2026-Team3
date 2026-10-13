import { config } from '../config.js'
import { one, query } from '../db/pool.js'
import { randomToken, sha256 } from '../lib/crypto.js'
import { forbidden, unauthorized } from '../lib/errors.js'
import { SESSION_TIMEOUTS, getSetting } from '../lib/settings.js'

export const SESSION_COOKIE = 'acadmate_session'
const REMEMBER_DAYS = 30
const SESSION_HOURS = 12

const cookieOptions = (maxAge) => ({
  httpOnly: true,
  secure: config.isProd,
  sameSite: 'lax',
  path: '/',
  ...(maxAge ? { maxAge } : {}),
})

// Creates a session row and sets the cookie. "Remember me" gives a 30-day persistent cookie; otherwise the
// cookie dies with the browser and the session also expires after the institution's idle timeout.
export async function startSession(req, res, user, { remember = false, db = { query } } = {}) {
  const token = randomToken()
  const ms = remember ? REMEMBER_DAYS * 86_400_000 : SESSION_HOURS * 3_600_000
  await db.query(
    `INSERT INTO sessions (user_id, token_hash, remember, expires_at, ip, user_agent)
     VALUES ($1, $2, $3, now() + $4 * interval '1 millisecond', $5, $6)`,
    [user.id, sha256(token), remember, ms, req.ip, req.get('user-agent')?.slice(0, 300) ?? null],
  )
  await db.query('UPDATE users SET last_login_at = now() WHERE id = $1', [user.id])
  res.cookie(SESSION_COOKIE, token, cookieOptions(remember ? ms : undefined))
}

export async function endSession(req, res) {
  const token = req.cookies?.[SESSION_COOKIE]
  if (token) await query('DELETE FROM sessions WHERE token_hash = $1', [sha256(token)])
  res.clearCookie(SESSION_COOKIE, cookieOptions())
}

// Attaches req.user when the request carries a valid, unexpired session for an active account.
export async function loadSession(req, res, next) {
  const token = req.cookies?.[SESSION_COOKIE]
  if (!token) return next()
  const row = await one(
    `SELECT s.id AS session_id, s.remember, s.last_seen_at, s.expires_at, u.*
       FROM sessions s JOIN users u ON u.id = s.user_id
      WHERE s.token_hash = $1`,
    [sha256(token)],
  )
  if (!row) return next()

  const security = await getSetting('security')
  const idleMinutes = SESSION_TIMEOUTS[security.sessionTimeout] ?? 120
  const idle = !row.remember && Date.now() - row.last_seen_at.getTime() > idleMinutes * 60_000
  if (row.expires_at.getTime() < Date.now() || idle || row.status !== 'active') {
    await query('DELETE FROM sessions WHERE id = $1', [row.session_id])
    res.clearCookie(SESSION_COOKIE, cookieOptions())
    return next()
  }
  // Touch at most once a minute to keep writes cheap.
  if (Date.now() - row.last_seen_at.getTime() > 60_000) {
    await query('UPDATE sessions SET last_seen_at = now() WHERE id = $1', [row.session_id])
  }
  const { session_id: sessionId, remember, last_seen_at: _seen, expires_at: _exp, password_hash: _ph, totp_secret: _ts, ...user } = row
  req.user = user
  req.sessionId = sessionId
  req.sessionRemember = remember
  next()
}

export function requireAuth(req, res, next) {
  if (!req.user) return next(unauthorized())
  next()
}

export const requireRole = (...roles) => (req, res, next) => {
  if (!req.user) return next(unauthorized())
  if (!roles.includes(req.user.role)) return next(forbidden())
  next()
}

// Reporting endpoints also accept an admin-issued API key: `Authorization: Bearer acm_...`.
export async function apiKeyAuth(req, res, next) {
  const header = req.get('authorization')
  if (req.user || !header?.startsWith('Bearer acm_')) return next()
  const key = await one(
    `SELECT k.id, u.* FROM api_keys k JOIN users u ON u.id = k.created_by
      WHERE k.key_hash = $1 AND k.revoked_at IS NULL AND u.status = 'active' AND u.role = 'admin'`,
    [sha256(header.slice('Bearer '.length).trim())],
  )
  if (!key) return next(unauthorized('Invalid API key.'))
  const { password_hash: _ph, totp_secret: _ts, ...user } = key
  req.user = { ...user, viaApiKey: true }
  next()
}

// API keys may only download the report exports; everything else needs a signed-in session.
const API_KEY_PATHS = new Set(['/overview/report', '/audit.csv'])
export function apiKeyScope(req, res, next) {
  if (req.user?.viaApiKey && !(req.method === 'GET' && API_KEY_PATHS.has(req.path))) {
    return next(forbidden('API keys can only download reports.'))
  }
  next()
}
